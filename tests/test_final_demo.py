import pytest
from sqlalchemy.orm import Session
from app.database.database import SessionLocal, init_db
from app.models.database_models import Lead, Call, TranscriptLine, ScheduledCallback, WhatsAppEvent
from app.services.voice.mock_voice_service import MockVoiceService
from app.services.conversation_service import ConversationService
from app.services.action_service import ActionService
from app.services.scheduler_service import SchedulerService

@pytest.fixture
def db_session():
    init_db()
    db = SessionLocal()
    db.query(WhatsAppEvent).delete()
    db.query(ScheduledCallback).delete()
    db.query(TranscriptLine).delete()
    db.query(Call).delete()
    db.query(Lead).delete()
    db.commit()
    yield db
    db.close()

@pytest.mark.asyncio
async def test_full_pipeline_hot_lead(db_session: Session):
    """
    End-to-end integration test for a HOT lead pipeline:
    Mock voice input -> conversation engine -> transcript persistence -> lead analysis -> HOT classification -> action trigger -> messaging abstraction event creation.
    """
    voice_service = MockVoiceService()
    phone = "9353352276"
    customer_name = "Surya"

    # 1. Start Call
    start_res = await voice_service.start_call(phone_number=phone, customer_name=customer_name)
    call_id = start_res["call_id"]
    assert call_id is not None

    # Verify initial call record in DB
    db_call = db_session.query(Call).filter(Call.call_id == call_id).first()
    assert db_call is not None
    assert db_call.phone_number == phone

    # 2. Turn 1: Product Discovery
    t1 = await voice_service.process_user_message(call_id, "I need an e-commerce website for 500 products.")
    assert "agent_response" in t1

    # 3. Turn 2: Budget & Timeline (Triggers HOT)
    t2 = await voice_service.process_user_message(call_id, "My budget is one lakh rupees and I need it within one month.")
    assert t2["classification"] == "HOT"

    # Verify Lead record updated in DB
    lead = db_session.query(Lead).filter(Lead.phone_number == phone).first()
    assert lead is not None
    assert lead.lead_classification == "HOT"
    assert lead.budget == "100000 INR"

    # Verify Transcripts stored in DB
    transcripts = db_session.query(TranscriptLine).filter(TranscriptLine.call_id == call_id).all()
    assert len(transcripts) >= 3  # Greeting + turns

    # Verify Messaging action recorded in DB
    messaging_events = db_session.query(WhatsAppEvent).filter(WhatsAppEvent.lead_id == lead.id).all()
    assert len(messaging_events) >= 1
    assert messaging_events[0].event_type == "HOT_LEAD_ALERT"

    # 4. End Call
    end_res = await voice_service.end_call(call_id)
    assert end_res["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_full_pipeline_warm_lead_callback(db_session: Session):
    """
    End-to-end integration test for a WARM lead pipeline:
    Mock voice input -> conversation engine -> transcript persistence -> barrier extraction -> natural callback expression parsing -> callback scheduling -> APScheduler record.
    """
    voice_service = MockVoiceService()
    phone = "9353352276"
    customer_name = "Surya"

    # 1. Start Call
    start_res = await voice_service.start_call(phone_number=phone, customer_name=customer_name)
    call_id = start_res["call_id"]

    # 2. Turn 1: Barrier & Callback Request
    t1 = await voice_service.process_user_message(
        call_id,
        "I want a website, but need to discuss the budget with my partner. Please call me tomorrow morning."
    )
    assert t1["classification"] == "WARM"

    # Verify Lead record
    lead = db_session.query(Lead).filter(Lead.phone_number == phone).first()
    assert lead is not None
    assert lead.lead_classification == "WARM"
    assert lead.objections_or_barriers is not None

    # Verify Scheduled Callback created in DB
    callbacks = db_session.query(ScheduledCallback).filter(ScheduledCallback.lead_id == lead.id).all()
    assert len(callbacks) >= 1
    cb = callbacks[0]
    assert cb.original_expression == "tomorrow morning"
    assert cb.status in ["SCHEDULED", "EXECUTED"]
    assert cb.scheduled_at is not None

    # 3. End Call
    end_res = await voice_service.end_call(call_id)
    assert end_res["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_full_pipeline_cold_lead(db_session: Session):
    """
    End-to-end integration test for a COLD lead pipeline:
    Mock voice input -> conversation engine -> COLD classification -> basic follow-up -> no HOT action.
    """
    voice_service = MockVoiceService()
    phone = "9353352276"
    customer_name = "Surya"

    start_res = await voice_service.start_call(phone_number=phone, customer_name=customer_name)
    call_id = start_res["call_id"]

    t1 = await voice_service.process_user_message(call_id, "I am just exploring options and browsing around.")
    assert t1["classification"] == "COLD"

    lead = db_session.query(Lead).filter(Lead.phone_number == phone).first()
    assert lead is not None
    assert lead.lead_classification == "COLD"

    # Verify NO HOT lead alerts were generated
    hot_alerts = db_session.query(WhatsAppEvent).filter(
        WhatsAppEvent.lead_id == lead.id,
        WhatsAppEvent.event_type == "HOT_LEAD_ALERT"
    ).all()
    assert len(hot_alerts) == 0

    end_res = await voice_service.end_call(call_id)
    assert end_res["status"] == "COMPLETED"
