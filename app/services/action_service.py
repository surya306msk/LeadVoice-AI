import os
import logging
import pytz
from datetime import datetime
from typing import Optional, Dict, Any, Union
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.database_models import Lead, WhatsAppEvent, ScheduledCallback
from app.models.schemas import LeadAnalysis
from app.services.messaging.messaging_factory import MessagingFactory
from app.services.message_builder_service import MessageBuilderService
from app.services.followup_service import FollowupService
from app.services.callback_parser_service import CallbackParserService
from app.services.llm_service import LLMService
from app.core.config import settings

logger = logging.getLogger("leadvoice.services.action_service")

class ActionService:
    """
    Action Engine service responsible for:
    - Receiving lead analysis
    - Classifying HOT / WARM / COLD
    - Triggering provider messaging (Telegram / WhatsApp / Mock)
    - Handling idempotency for duplicate HOT lead alerts
    - Managing scheduled callbacks for WARM leads
    - Sending optional resume/architecture attachments
    - Recording database events
    """

    def __init__(self):
        self.message_builder = MessageBuilderService()
        self.followup_service = FollowupService()
        self.callback_parser = CallbackParserService()
        self.llm_service = LLMService()

    async def process_lead_action(
        self,
        db: Optional[Session] = None,
        lead_id: Optional[int] = None,
        call_id: Optional[str] = None,
        analysis: Optional[Union[LeadAnalysis, dict]] = None,
        conversation: Optional[str] = None,
        provider: Optional[str] = None,
        recipient: Optional[str] = None
    ) -> Dict[str, Any]:
        
        close_db_on_exit = False
        if db is None:
            db = SessionLocal()
            close_db_on_exit = True

        try:
            # 1. Fetch Lead record if lead_id provided
            lead = None
            if lead_id is not None:
                lead = db.query(Lead).filter(Lead.id == lead_id).first()

            # 2. Derive LeadAnalysis if missing but conversation provided
            if analysis is None and conversation and conversation.strip():
                analysis = await self.llm_service.analyze_conversation(conversation)

            if analysis is None and lead:
                # Construct synthetic analysis from lead attributes
                analysis = LeadAnalysis(
                    language=lead.detected_language,
                    business_type=lead.business_type,
                    products=lead.products_sold,
                    product_count=lead.approximate_product_count,
                    budget=lead.budget,
                    timeline=lead.timeline,
                    features=lead.required_features.split(",") if lead.required_features else [],
                    decision_maker=lead.decision_maker,
                    barrier=lead.objections_or_barriers,
                    callback_requested=bool(lead.callback_request),
                    callback_expression=lead.callback_request,
                    lead_status=lead.lead_classification or "COLD",
                    confidence=1.0,
                    reason=lead.reason_for_classification or "DB record lookup",
                    recommended_action="SEND_WHATSAPP_NOW" if lead.lead_classification == "HOT" else "SEND_FOLLOWUP",
                    conversation_summary=lead.conversation_summary or ""
                )

            if analysis is None:
                return {
                    "success": False,
                    "already_processed": False,
                    "status": "FAILED",
                    "error": "No lead analysis or conversation provided"
                }

            # Normalize analysis object
            if isinstance(analysis, dict):
                analysis_obj = LeadAnalysis(**analysis)
            else:
                analysis_obj = analysis

            classification = analysis_obj.lead_status.upper()

            # Update Lead in DB if lead exists
            if lead:
                lead.lead_classification = classification
                lead.reason_for_classification = analysis_obj.reason
                if analysis_obj.conversation_summary:
                    lead.conversation_summary = analysis_obj.conversation_summary
                db.commit()

            # 3. Check Idempotency for HOT lead alerts
            if classification == "HOT" and lead_id is not None:
                existing_event = db.query(WhatsAppEvent).filter(
                    WhatsAppEvent.lead_id == lead_id,
                    WhatsAppEvent.event_type == "HOT_LEAD_ALERT",
                    WhatsAppEvent.status.in_(["SENT", "MOCK_SENT"])
                ).first()

                if existing_event:
                    logger.info(f"Idempotent skip: HOT lead alert already sent for lead_id={lead_id}")
                    return {
                        "success": True,
                        "already_processed": True,
                        "status": "idempotent_skipped",
                        "lead_id": lead_id,
                        "classification": "HOT",
                        "action_taken": "HOT_LEAD_ALERT",
                        "provider": existing_event.provider,
                        "event_id": existing_event.id,
                        "message": "HOT lead alert already processed for this lead",
                        "attachments": {}
                    }

            # 4. Resolve messaging provider
            messaging_service = MessagingFactory.get_messaging_service(provider)
            selected_provider = (provider or settings.MESSAGING_PROVIDER or "telegram").lower()

            # Resolve target recipient (phone or chat_id)
            target_recipient = recipient
            if not target_recipient and lead:
                target_recipient = lead.phone_number

            # 5. Handle Callback Scheduling for WARM leads
            callback_time_str = None
            if classification == "WARM" and (analysis_obj.callback_requested or analysis_obj.callback_expression):
                cb_expr = analysis_obj.callback_expression or "tomorrow morning"
                parse_res = await self.callback_parser.parse_callback(cb_expr)
                if parse_res.scheduled_at:
                    callback_time_str = parse_res.scheduled_at.strftime("%Y-%m-%d %H:%M %Z")
                    if lead:
                        # Cancel existing pending callbacks for this lead
                        db.query(ScheduledCallback).filter(
                            ScheduledCallback.lead_id == lead.id,
                            ScheduledCallback.status == "SCHEDULED"
                        ).update({"status": "CANCELLED"})
                        db.commit()

                        # Save new callback
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

            # 6. Build Personalized Message
            if classification == "HOT":
                event_type = "HOT_LEAD_ALERT"
                msg_text = self.message_builder.build_hot_lead_alert(analysis_obj, lead)
            elif classification == "WARM":
                event_type = "POST_CALL_FOLLOWUP"
                msg_text = self.followup_service.generate_followup(analysis_obj, lead, callback_time_str)
            else: # COLD
                event_type = "POST_CALL_FOLLOWUP"
                msg_text = self.followup_service.generate_followup(analysis_obj, lead)

            # 7. Create DB event record
            event_record = WhatsAppEvent(
                lead_id=lead.id if lead else (lead_id or 0),
                call_id=call_id,
                provider=selected_provider,
                event_type=event_type,
                recipient=target_recipient or "",
                phone_number=target_recipient or "",
                message_type=event_type,
                message=msg_text,
                content=msg_text,
                status="PENDING"
            )
            db.add(event_record)
            db.commit()
            db.refresh(event_record)

            # 8. Send Message via provider
            send_res = await messaging_service.send_message(
                recipient=target_recipient or "",
                text=msg_text
            )

            attachment_results = {}

            if send_res.get("success"):
                is_mock = settings.MOCK_MODE or send_res.get("provider") == "mock" or str(send_res.get("provider_message_id", "")).startswith("mock_")
                final_status = "MOCK_SENT" if is_mock else "SENT"
                
                event_record.status = final_status
                event_record.provider_message_id = send_res.get("provider_message_id")
                if lead:
                    lead.whatsapp_sent = True
                db.commit()

                # 9. Handle optional Attachments for HOT leads or configured files
                if settings.RESUME_FILE_PATH:
                    att_res = await self._send_attachment(
                        db=db,
                        messaging_service=messaging_service,
                        provider=selected_provider,
                        lead_id=lead.id if lead else (lead_id or 0),
                        call_id=call_id,
                        recipient=target_recipient or "",
                        event_type="RESUME_ATTACHMENT",
                        file_path=settings.RESUME_FILE_PATH,
                        is_document=True
                    )
                    attachment_results["resume"] = att_res

                if settings.ARCHITECTURE_IMAGE_PATH:
                    att_res = await self._send_attachment(
                        db=db,
                        messaging_service=messaging_service,
                        provider=selected_provider,
                        lead_id=lead.id if lead else (lead_id or 0),
                        call_id=call_id,
                        recipient=target_recipient or "",
                        event_type="ARCHITECTURE_ATTACHMENT",
                        file_path=settings.ARCHITECTURE_IMAGE_PATH,
                        is_document=False
                    )
                    attachment_results["architecture"] = att_res

                return {
                    "success": True,
                    "already_processed": False,
                    "status": final_status,
                    "lead_id": lead.id if lead else lead_id,
                    "classification": classification,
                    "action_taken": event_type,
                    "provider": send_res.get("provider", selected_provider),
                    "event_id": event_record.id,
                    "provider_message_id": send_res.get("provider_message_id"),
                    "message": msg_text,
                    "attachments": attachment_results,
                    "error": None
                }
            else:
                event_record.status = "FAILED"
                event_record.error_message = send_res.get("error")
                db.commit()

                return {
                    "success": False,
                    "already_processed": False,
                    "status": "FAILED",
                    "lead_id": lead.id if lead else lead_id,
                    "classification": classification,
                    "action_taken": event_type,
                    "provider": send_res.get("provider", selected_provider),
                    "event_id": event_record.id,
                    "provider_message_id": None,
                    "message": msg_text,
                    "attachments": {},
                    "error": send_res.get("error")
                }

        finally:
            if close_db_on_exit:
                db.close()

    async def _send_attachment(
        self,
        db: Session,
        messaging_service: Any,
        provider: str,
        lead_id: int,
        call_id: Optional[str],
        recipient: str,
        event_type: str,
        file_path: str,
        is_document: bool
    ) -> str:
        att_event = WhatsAppEvent(
            lead_id=lead_id,
            call_id=call_id,
            provider=provider,
            event_type=event_type,
            recipient=recipient,
            phone_number=recipient,
            message_type=event_type,
            message=f"Attachment: {file_path}",
            content=f"Attachment: {file_path}",
            status="PENDING"
        )
        db.add(att_event)
        db.commit()
        db.refresh(att_event)

        try:
            if is_document:
                res = await messaging_service.send_document(
                    recipient=recipient,
                    document_path=file_path,
                    caption=f"{event_type.replace('_', ' ').title()}"
                )
            else:
                res = await messaging_service.send_image(
                    recipient=recipient,
                    image_path=file_path,
                    caption=f"{event_type.replace('_', ' ').title()}"
                )

            if res.get("success"):
                is_mock = settings.MOCK_MODE or res.get("provider") == "mock" or str(res.get("provider_message_id", "")).startswith("mock_")
                att_status = "MOCK_SENT" if is_mock else "SENT"
                att_event.status = att_status
                att_event.provider_message_id = res.get("provider_message_id")
                db.commit()
                return att_status
            else:
                att_event.status = "FAILED"
                att_event.error_message = res.get("error")
                db.commit()
                logger.error(f"Attachment send failed for {file_path}: {res.get('error')}")
                return "FAILED"
        except Exception as e:
            att_event.status = "FAILED"
            att_event.error_message = str(e)
            db.commit()
            logger.error(f"Attachment exception for {file_path}: {e}")
            return "FAILED"
