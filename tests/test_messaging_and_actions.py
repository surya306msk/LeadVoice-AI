import os
import pytest
from unittest.mock import AsyncMock, patch
import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.database import SessionLocal, init_db
from app.models.database_models import Lead, WhatsAppEvent, ScheduledCallback
from app.models.schemas import LeadAnalysis
from app.services.messaging.telegram_service import TelegramService
from app.services.messaging.whatsapp_service import WhatsAppService
from app.services.messaging.messaging_factory import MessagingFactory, MockMessagingService
from app.services.messaging.base_messaging_service import BaseMessagingService
from app.services.action_service import ActionService
from app.services.followup_service import FollowupService
from app.services.message_builder_service import MessageBuilderService
from app.core.config import settings

client = TestClient(app)

@pytest.fixture
def db_session():
    init_db()
    db = SessionLocal()
    yield db
    db.close()

@pytest.fixture
def test_lead(db_session: Session):
    # Clean prior events & leads for deterministic testing
    db_session.query(WhatsAppEvent).delete()
    db_session.query(ScheduledCallback).delete()
    db_session.query(Lead).delete()
    db_session.commit()

    lead = Lead(
        customer_name="Surya",
        phone_number="9353352276",
        business_type="E-commerce Store",
        products_sold="Sports Shoes",
        approximate_product_count=150,
        budget="50000 INR",
        timeline="2 weeks",
        required_features="Payment Gateway, Order Tracking",
        lead_classification="HOT"
    )
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)
    return lead


# 1. Telegram mock message
@pytest.mark.asyncio
async def test_telegram_mock_message():
    tg_service = TelegramService(mock_mode=True)
    res = await tg_service.send_message(recipient="123456", text="Hello from Telegram mock")
    assert res["success"] is True
    assert res["provider"] == "telegram"
    assert res["provider_message_id"].startswith("mock_tg_msg_")
    assert res["error"] is None


# 2. Telegram mock document
@pytest.mark.asyncio
async def test_telegram_mock_document():
    tg_service = TelegramService(mock_mode=True)
    res = await tg_service.send_document(recipient="123456", document_path="sample_resume.pdf", caption="Resume")
    assert res["success"] is True
    assert res["provider"] == "telegram"
    assert res["provider_message_id"].startswith("mock_tg_doc_")
    assert res["error"] is None


# 3. Telegram mock image
@pytest.mark.asyncio
async def test_telegram_mock_image():
    tg_service = TelegramService(mock_mode=True)
    res = await tg_service.send_image(recipient="123456", image_path="architecture.png", caption="Architecture")
    assert res["success"] is True
    assert res["provider"] == "telegram"
    assert res["provider_message_id"].startswith("mock_tg_img_")
    assert res["error"] is None


# 4. WhatsApp mock message
@pytest.mark.asyncio
async def test_whatsapp_mock_message():
    wa_service = WhatsAppService(mock_mode=True)
    res = await wa_service.send_message(recipient="+1234567890", text="Hello from WhatsApp mock")
    assert res["success"] is True
    assert res["provider"] == "whatsapp"
    assert res["provider_message_id"].startswith("mock_wa_msg_")
    assert res["error"] is None


# 5. Messaging factory
def test_messaging_factory():
    tg = MessagingFactory.get_messaging_service("telegram")
    assert isinstance(tg, TelegramService)

    wa = MessagingFactory.get_messaging_service("whatsapp")
    assert isinstance(wa, WhatsAppService)

    mock_svc = MessagingFactory.get_messaging_service("mock")
    assert isinstance(mock_svc, MockMessagingService)


# 6. HOT lead action
@pytest.mark.asyncio
async def test_hot_lead_action(test_lead):
    action_svc = ActionService()
    hot_analysis = LeadAnalysis(
        language="English",
        business_type="E-commerce Store",
        products="Sports Shoes",
        product_count=150,
        budget="50000 INR",
        timeline="2 weeks",
        features=["Payment Gateway"],
        lead_status="HOT",
        confidence=0.95,
        reason="High budget and clear urgency",
        recommended_action="SEND_WHATSAPP_NOW",
        conversation_summary="Customer wants to launch e-commerce store in 2 weeks."
    )
    res = await action_svc.process_lead_action(
        lead_id=test_lead.id,
        analysis=hot_analysis,
        provider="telegram"
    )
    assert res["success"] is True
    assert res["classification"] == "HOT"
    assert res["action_taken"] == "HOT_LEAD_ALERT"
    assert res["already_processed"] is False
    assert res["event_id"] is not None


# 7. WARM lead action
@pytest.mark.asyncio
async def test_warm_lead_action(test_lead):
    action_svc = ActionService()
    warm_analysis = LeadAnalysis(
        language="English",
        business_type="Retail",
        barrier="Needs partner approval for budget",
        callback_requested=True,
        callback_expression="tomorrow morning",
        lead_status="WARM",
        confidence=0.85,
        reason="Needs partner approval",
        recommended_action="SCHEDULE_CALLBACK",
        conversation_summary="Interested customer needing partner sign-off."
    )
    res = await action_svc.process_lead_action(
        lead_id=test_lead.id,
        analysis=warm_analysis,
        provider="telegram"
    )
    assert res["success"] is True
    assert res["classification"] == "WARM"
    assert res["action_taken"] == "POST_CALL_FOLLOWUP"


# 8. COLD lead action
@pytest.mark.asyncio
async def test_cold_lead_action(test_lead):
    action_svc = ActionService()
    cold_analysis = LeadAnalysis(
        language="English",
        lead_status="COLD",
        confidence=0.70,
        reason="Just exploring options",
        recommended_action="SEND_FOLLOWUP",
        conversation_summary="Customer inquired without immediate purchase intent."
    )
    res = await action_svc.process_lead_action(
        lead_id=test_lead.id,
        analysis=cold_analysis,
        provider="telegram"
    )
    assert res["success"] is True
    assert res["classification"] == "COLD"
    assert res["action_taken"] == "POST_CALL_FOLLOWUP"


# 9. Duplicate HOT action (Idempotency test)
@pytest.mark.asyncio
async def test_duplicate_hot_action(test_lead):
    action_svc = ActionService()
    hot_analysis = LeadAnalysis(
        language="English",
        lead_status="HOT",
        confidence=0.9,
        reason="Immediate need",
        recommended_action="SEND_WHATSAPP_NOW",
        conversation_summary="Immediate deployment requested."
    )

    # First call
    res1 = await action_svc.process_lead_action(
        lead_id=test_lead.id,
        analysis=hot_analysis,
        provider="telegram"
    )
    assert res1["success"] is True
    assert res1["already_processed"] is False

    # Second duplicate call for same HOT lead
    res2 = await action_svc.process_lead_action(
        lead_id=test_lead.id,
        analysis=hot_analysis,
        provider="telegram"
    )
    assert res2["success"] is True
    assert res2["already_processed"] is True
    assert res2["status"] == "idempotent_skipped"


# 10. Personalized follow-up
def test_personalized_followup(test_lead):
    builder = MessageBuilderService()
    hot_analysis = LeadAnalysis(
        business_type="Automotive",
        products="Spare Parts",
        product_count=500,
        budget="200000 INR",
        timeline="1 month",
        lead_status="HOT",
        confidence=0.9,
        reason="High volume order",
        recommended_action="SEND_WHATSAPP_NOW",
        conversation_summary="Bulk order inquiry"
    )
    hot_msg = builder.build_hot_lead_alert(hot_analysis, test_lead)
    assert "Surya" in hot_msg
    assert "Automotive" in hot_msg
    assert "Spare Parts" in hot_msg
    assert "200000 INR" in hot_msg

    followup_svc = FollowupService()
    warm_msg = followup_svc.generate_followup(
        analysis={"lead_status": "WARM", "barrier": "Budget constraint"},
        lead=test_lead,
        callback_time_str="2026-08-29 10:00 IST"
    )
    assert "Surya" in warm_msg
    assert "Budget constraint" in warm_msg
    assert "2026-08-29 10:00 IST" in warm_msg


# 11. Missing recipient
@pytest.mark.asyncio
async def test_missing_recipient():
    tg_service = TelegramService(mock_mode=False, bot_token="dummy_token", chat_id="")
    res = await tg_service.send_message(recipient="", text="Test")
    assert res["success"] is False
    assert "Missing recipient" in res["error"]


# 12. Missing attachment
@pytest.mark.asyncio
async def test_missing_attachment():
    tg_service = TelegramService(mock_mode=False, bot_token="dummy_token", chat_id="12345")
    res = await tg_service.send_document(recipient="12345", document_path="non_existent_file_path.pdf")
    assert res["success"] is False
    assert "file not found" in res["error"].lower()


# 13. Provider failure handling
@pytest.mark.asyncio
async def test_provider_failure():
    tg_service = TelegramService(mock_mode=False, bot_token="fake_token", chat_id="12345")
    
    # Mock httpx response failure (500 Server Error)
    mock_response = httpx.Response(status_code=500, text="Internal Server Error")
    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        res = await tg_service.send_message(recipient="12345", text="Test")
        assert res["success"] is False
        assert "HTTP 500" in res["error"]


# 14. MOCK_MODE behavior
@pytest.mark.asyncio
async def test_mock_mode_behavior(test_lead):
    # Ensure MOCK_MODE is enabled
    with patch.object(settings, "MOCK_MODE", True):
        action_svc = ActionService()
        res = await action_svc.process_lead_action(
            lead_id=test_lead.id,
            conversation="I need 100 products website in 1 month with 1 lakh budget.",
            provider="telegram"
        )
        assert res["success"] is True
        assert res["status"] == "MOCK_SENT"


# API Endpoint Tests
def test_api_messaging_test():
    response = client.post(
        "/api/messaging/test",
        json={"provider": "telegram", "message": "API test message"}
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

def test_api_whatsapp_test():
    response = client.post(
        "/api/whatsapp/test",
        json={"message": "WhatsApp API test"}
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

def test_api_actions_process_lead(test_lead):
    response = client.post(
        "/api/actions/process-lead",
        json={
            "lead_id": test_lead.id,
            "conversation": "I want an e-commerce website for 200 products. My budget is around one lakh and I need it within one month.",
            "provider": "telegram"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["classification"] == "HOT"
