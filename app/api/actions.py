import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.schemas import (
    MessagingTestRequest,
    ProcessLeadActionRequest,
    ActionProcessResponse,
    WhatsAppFollowupRequest
)
from app.services.action_service import ActionService
from app.services.messaging.messaging_factory import MessagingFactory
from app.core.config import settings

router = APIRouter(prefix="/api")
logger = logging.getLogger("leadvoice.api.actions")

def get_action_service():
    return ActionService()

@router.post("/messaging/test")
async def test_messaging(
    payload: MessagingTestRequest,
    db: Session = Depends(get_db)
):
    """
    Generic test endpoint for messaging providers (Telegram, WhatsApp, Mock).
    Supports sending text, document, or image.
    """
    provider = payload.provider or settings.MESSAGING_PROVIDER
    service = MessagingFactory.get_messaging_service(provider)
    recipient = payload.recipient or ""

    if payload.msg_type == "document":
        file_path = payload.file_path or settings.RESUME_FILE_PATH or "dummy_resume.pdf"
        res = await service.send_document(recipient=recipient, document_path=file_path, caption=payload.message)
    elif payload.msg_type == "image":
        file_path = payload.file_path or settings.ARCHITECTURE_IMAGE_PATH or "dummy_arch.png"
        res = await service.send_image(recipient=recipient, image_path=file_path, caption=payload.message)
    else:
        res = await service.send_message(recipient=recipient, text=payload.message or "Test message")

    return res

@router.post("/whatsapp/test")
async def test_whatsapp(
    payload: MessagingTestRequest,
    db: Session = Depends(get_db)
):
    """
    Backward-compatible WhatsApp test endpoint.
    """
    provider = payload.provider or "whatsapp"
    service = MessagingFactory.get_messaging_service(provider)
    recipient = payload.recipient or settings.WHATSAPP_RECIPIENT_PHONE or ""

    res = await service.send_message(recipient=recipient, text=payload.message or "WhatsApp test message")
    return res

@router.post("/actions/process-lead", response_model=ActionProcessResponse)
async def process_lead_action(
    payload: ProcessLeadActionRequest,
    db: Session = Depends(get_db),
    action_service: ActionService = Depends(get_action_service)
):
    """
    Trigger action engine: classify, build personalized message, send via messaging provider,
    schedule callbacks, and enforce idempotency.
    """
    result = await action_service.process_lead_action(
        db=db,
        lead_id=payload.lead_id,
        call_id=payload.call_id,
        analysis=payload.analysis,
        conversation=payload.conversation,
        provider=payload.provider,
        recipient=payload.recipient
    )

    return ActionProcessResponse(**result)

@router.post("/whatsapp/followup")
async def send_whatsapp_followup(
    payload: WhatsAppFollowupRequest,
    db: Session = Depends(get_db),
    action_service: ActionService = Depends(get_action_service)
):
    """
    Trigger follow-up action for a lead.
    """
    result = await action_service.process_lead_action(
        db=db,
        lead_id=payload.lead_id,
        provider=payload.provider or "whatsapp"
    )
    return result
