import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.schemas import (
    StartMockCallRequest,
    StartMockCallResponse,
    MockCallMessageRequest,
    MockCallMessageResponse,
    EndMockCallRequest,
    EndMockCallResponse,
    VoiceWebhookRequest
)
from app.services.voice.voice_factory import VoiceFactory
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/api/voice")
logger = logging.getLogger("leadvoice.api.voice")

@router.post("/webhook")
async def voice_provider_webhook(
    payload: VoiceWebhookRequest,
    db: Session = Depends(get_db)
):
    """
    Integration-ready telephony webhook endpoint.
    Converts voice provider events (call_started, transcript, call_ended)
    into standard ConversationService actions.
    """
    conv_service = ConversationService()
    event_type = payload.event_type.lower()

    if event_type == "call_started":
        if not payload.phone_number:
            raise HTTPException(status_code=400, detail="phone_number is required for call_started event")
        res = await conv_service.start_call(
            phone_number=payload.phone_number,
            customer_name=payload.customer_name,
            db=db
        )
        return {"success": True, "event": "call_started", "data": res}

    elif event_type == "transcript":
        if not payload.call_id or not payload.message:
            raise HTTPException(status_code=400, detail="call_id and message are required for transcript event")
        res = await conv_service.process_user_turn(
            call_id=payload.call_id,
            user_message=payload.message,
            db=db
        )
        return {"success": True, "event": "transcript", "data": res}

    elif event_type == "call_ended":
        if not payload.call_id:
            raise HTTPException(status_code=400, detail="call_id is required for call_ended event")
        res = await conv_service.end_call(
            call_id=payload.call_id,
            db=db
        )
        return {"success": True, "event": "call_ended", "data": res}

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported event_type '{payload.event_type}'")

@router.post("/mock/start", response_model=StartMockCallResponse)
async def start_mock_call(
    payload: StartMockCallRequest,
    db: Session = Depends(get_db)
):
    voice_service = VoiceFactory.get_voice_service(payload.provider or "mock")
    res = await voice_service.start_call(
        phone_number=payload.phone_number,
        customer_name=payload.customer_name,
        language=payload.language
    )
    return StartMockCallResponse(**res)

@router.post("/mock/message", response_model=MockCallMessageResponse)
async def process_mock_message(
    payload: MockCallMessageRequest,
    db: Session = Depends(get_db)
):
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="User message cannot be empty.")

    voice_service = VoiceFactory.get_voice_service("mock")
    res = await voice_service.process_user_message(
        call_id=payload.call_id,
        message=payload.message
    )
    if "error" in res:
        raise HTTPException(status_code=res.get("status_code", 404), detail=res["error"])

    return MockCallMessageResponse(**res)

@router.post("/mock/end", response_model=EndMockCallResponse)
async def end_mock_call(
    payload: EndMockCallRequest,
    db: Session = Depends(get_db)
):
    voice_service = VoiceFactory.get_voice_service("mock")
    res = await voice_service.end_call(call_id=payload.call_id)
    if "error" in res:
        raise HTTPException(status_code=res.get("status_code", 404), detail=res["error"])

    return EndMockCallResponse(**res)

@router.get("/calls/{call_id}")
async def get_call_details(
    call_id: str,
    db: Session = Depends(get_db)
):
    conv_service = ConversationService()
    res = conv_service.get_call_details(call_id=call_id, db=db)
    if "error" in res:
        raise HTTPException(status_code=res.get("status_code", 404), detail=res["error"])

    return res
