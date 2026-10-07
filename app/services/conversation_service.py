import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.database_models import Lead, Call, TranscriptLine, ScheduledCallback, WhatsAppEvent
from app.models.schemas import LeadAnalysis
from app.services.llm_service import LLMService
from app.services.conversation_engine import ConversationEngine
from app.services.action_service import ActionService
from app.services.callback_parser_service import CallbackParserService

logger = logging.getLogger("leadvoice.services.conversation_service")

class ConversationService:
    """
    Stateful Conversation & Session Service.
    Persists call records, transcript lines, progressively updates LeadAnalysis,
    triggers real-time Phase 4 Action Engine when lead becomes HOT, and manages callbacks.
    """

    def __init__(self):
        self.llm_service = LLMService()
        self.engine = ConversationEngine()
        self.action_service = ActionService()
        self.callback_parser = CallbackParserService()

    async def start_call(
        self,
        phone_number: str,
        customer_name: Optional[str] = None,
        db: Optional[Session] = None,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            # 1. Find or create Lead
            lead = db.query(Lead).filter(Lead.phone_number == phone_number).first()
            if not lead:
                lead = Lead(
                    phone_number=phone_number,
                    customer_name=customer_name,
                    detected_language=language or "English",
                    lead_classification="COLD"
                )
                db.add(lead)
                db.commit()
                db.refresh(lead)
            elif customer_name and not lead.customer_name:
                lead.customer_name = customer_name
                db.commit()

            # 2. Create Call record
            call_id = f"call_{uuid.uuid4().hex[:12]}"
            call = Call(
                call_id=call_id,
                phone_number=phone_number,
                status="IN_PROGRESS",
                start_time=datetime.utcnow(),
                detected_language=language or lead.detected_language or "English",
                lead_id=lead.id
            )
            db.add(call)
            db.commit()
            db.refresh(call)

            # Initial Agent Greeting
            greeting = "Hello! Thank you for calling LeadVoice AI. How can I help you today?"
            if language == "Telugu" or (lead.detected_language and "telugu" in lead.detected_language.lower()):
                greeting = "Namaskaram! LeadVoice AI ki swagatam. Nenu meeku ela sahayapadalenu?"
            elif language == "Hindi" or (lead.detected_language and "hindi" in lead.detected_language.lower()):
                greeting = "Namaste! LeadVoice AI me aapka swagat hai. Main aapki kya sahayata kar sakta hoon?"

            # Record agent greeting in transcripts
            tx_line = TranscriptLine(
                call_id=call_id,
                speaker="agent",
                text=greeting,
                language=language or "English"
            )
            db.add(tx_line)
            db.commit()

            return {
                "call_id": call_id,
                "lead_id": lead.id,
                "phone_number": phone_number,
                "status": "IN_PROGRESS",
                "greeting": greeting,
                "message": "Call started successfully"
            }
        finally:
            if close_db:
                db.close()

    async def process_user_turn(
        self,
        call_id: str,
        user_message: str,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            call = db.query(Call).filter(Call.call_id == call_id).first()
            if not call:
                return {
                    "error": f"Call session '{call_id}' not found",
                    "status_code": 404
                }

            lead = db.query(Lead).filter(Lead.id == call.lead_id).first()

            # 1. Record customer turn in transcripts
            tx_cust = TranscriptLine(
                call_id=call_id,
                speaker="customer",
                text=user_message,
                timestamp=datetime.utcnow()
            )
            db.add(tx_cust)
            db.commit()

            # 2. Reconstruct full transcript string
            all_transcripts = db.query(TranscriptLine).filter(TranscriptLine.call_id == call_id).order_by(TranscriptLine.timestamp.asc()).all()
            transcript_lines = [f"{t.speaker.upper()}: {t.text}" for t in all_transcripts]
            full_transcript = "\n".join(transcript_lines)

            # 3. Progressive Lead Analysis via LLM Service
            existing_lead_dict = None
            if lead:
                existing_lead_dict = {
                    "language": lead.detected_language,
                    "business_type": lead.business_type,
                    "products": lead.products_sold,
                    "product_count": lead.approximate_product_count,
                    "budget": lead.budget,
                    "timeline": lead.timeline,
                    "features": lead.required_features.split(",") if lead.required_features else [],
                    "decision_maker": lead.decision_maker,
                    "barrier": lead.objections_or_barriers,
                    "callback_requested": bool(lead.callback_request),
                    "callback_expression": lead.callback_request,
                    "lead_status": lead.lead_classification or "COLD"
                }

            analysis: LeadAnalysis = await self.llm_service.analyze_conversation(
                conversation=full_transcript,
                existing_lead_data=existing_lead_dict
            )

            # 4. Generate natural agent response using ConversationEngine
            eng_res = self.engine.generate_response(
                user_message=user_message,
                conversation_history=[{"speaker": t.speaker, "text": t.text} for t in all_transcripts],
                analysis=analysis,
                language=call.detected_language
            )

            agent_response_text = eng_res["agent_response"]
            detected_lang = eng_res["language"]

            # Update detected language on Call and Lead
            call.detected_language = detected_lang
            if lead:
                lead.detected_language = detected_lang
                lead.business_type = analysis.business_type or lead.business_type
                lead.products_sold = analysis.products or lead.products_sold
                lead.approximate_product_count = analysis.product_count or lead.approximate_product_count
                lead.budget = analysis.budget or lead.budget
                lead.timeline = analysis.timeline or lead.timeline
                lead.objections_or_barriers = analysis.barrier or lead.objections_or_barriers
                lead.callback_request = analysis.callback_expression or lead.callback_request
                lead.lead_classification = analysis.lead_status
                lead.reason_for_classification = analysis.reason
                lead.conversation_summary = analysis.conversation_summary
                db.commit()

            # 5. Record agent turn in transcripts
            tx_agent = TranscriptLine(
                call_id=call_id,
                speaker="agent",
                text=agent_response_text,
                language=detected_lang,
                timestamp=datetime.utcnow()
            )
            db.add(tx_agent)
            db.commit()

            # 6. Trigger Real-Time Phase 4 Action if HOT
            action_result = None
            if analysis.lead_status == "HOT" and lead:
                action_result = await self.action_service.process_lead_action(
                    db=db,
                    lead_id=lead.id,
                    call_id=call_id,
                    analysis=analysis
                )

            # 7. Schedule Callback if WARM and callback requested
            if analysis.lead_status == "WARM" and (analysis.callback_requested or analysis.callback_expression) and lead:
                cb_expr = analysis.callback_expression or "tomorrow morning"
                parse_res = await self.callback_parser.parse_callback(cb_expr)
                if parse_res.scheduled_at:
                    db.query(ScheduledCallback).filter(
                        ScheduledCallback.lead_id == lead.id,
                        ScheduledCallback.status == "SCHEDULED"
                    ).update({"status": "CANCELLED"})
                    db.commit()

                    new_cb = ScheduledCallback(
                        lead_id=lead.id,
                        call_id=call_id,
                        original_expression=cb_expr,
                        scheduled_at=parse_res.scheduled_at,
                        timezone=parse_res.timezone,
                        status="SCHEDULED",
                        assumption=parse_res.assumption
                    )
                    db.add(new_cb)
                    db.commit()

            return {
                "call_id": call_id,
                "agent_response": agent_response_text,
                "language": detected_lang,
                "classification": analysis.lead_status,
                "action_triggered": action_result.get("action_taken") if action_result else None,
                "lead_analysis": analysis.dict()
            }
        finally:
            if close_db:
                db.close()

    async def end_call(
        self,
        call_id: str,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            call = db.query(Call).filter(Call.call_id == call_id).first()
            if not call:
                return {
                    "error": f"Call session '{call_id}' not found",
                    "status_code": 404
                }

            call.status = "COMPLETED"
            call.end_time = datetime.utcnow()
            if call.start_time:
                call.duration = int((call.end_time - call.start_time).total_seconds())

            lead = db.query(Lead).filter(Lead.id == call.lead_id).first()

            # Execute post-call follow-up for WARM or COLD leads if not already sent
            followup_result = None
            if lead and lead.lead_classification in ["WARM", "COLD"]:
                followup_result = await self.action_service.process_lead_action(
                    db=db,
                    lead_id=lead.id,
                    call_id=call_id
                )

            db.commit()

            return {
                "call_id": call_id,
                "status": "COMPLETED",
                "duration_seconds": call.duration,
                "lead_id": lead.id if lead else None,
                "classification": lead.lead_classification if lead else "COLD",
                "followup_status": followup_result.get("status") if followup_result else None,
                "summary": lead.conversation_summary if lead else None
            }
        finally:
            if close_db:
                db.close()

    def get_call_details(self, call_id: str, db: Optional[Session] = None) -> Dict[str, Any]:
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            call = db.query(Call).filter(Call.call_id == call_id).first()
            if not call:
                return {
                    "error": f"Call session '{call_id}' not found",
                    "status_code": 404
                }

            transcripts = db.query(TranscriptLine).filter(TranscriptLine.call_id == call_id).order_by(TranscriptLine.timestamp.asc()).all()
            lead = db.query(Lead).filter(Lead.id == call.lead_id).first()

            return {
                "call_id": call.call_id,
                "phone_number": call.phone_number,
                "status": call.status,
                "start_time": call.start_time,
                "end_time": call.end_time,
                "duration": call.duration,
                "detected_language": call.detected_language,
                "lead": {
                    "id": lead.id,
                    "customer_name": lead.customer_name,
                    "phone_number": lead.phone_number,
                    "classification": lead.lead_classification,
                    "business_type": lead.business_type,
                    "products_sold": lead.products_sold,
                    "budget": lead.budget,
                    "timeline": lead.timeline,
                    "reason": lead.reason_for_classification
                } if lead else None,
                "transcripts": [
                    {
                        "speaker": t.speaker,
                        "text": t.text,
                        "timestamp": t.timestamp
                    } for t in transcripts
                ]
            }
        finally:
            if close_db:
                db.close()
