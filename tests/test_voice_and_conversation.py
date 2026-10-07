import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.database import SessionLocal, init_db
from app.models.database_models import Lead, Call, TranscriptLine, ScheduledCallback, WhatsAppEvent
from app.services.voice.voice_factory import VoiceFactory
from app.services.voice.mock_voice_service import MockVoiceService
from app.services.voice.retell_voice_service import RetellVoiceService
from app.services.conversation_service import ConversationService

client = TestClient(app)

@pytest.fixture
def db_session():
    init_db()
    db = SessionLocal()
    # clean tables
    db.query(WhatsAppEvent).delete()
    db.query(ScheduledCallback).delete()
    db.query(TranscriptLine).delete()
    db.query(Call).delete()
    db.query(Lead).delete()
    db.commit()
    yield db
    db.close()


# 1. Mock call start
@pytest.mark.asyncio
async def test_mock_call_start(db_session):
    voice_svc = MockVoiceService()
    res = await voice_svc.start_call(phone_number="+919999999999", customer_name="Test User")
    assert "call_id" in res
    assert res["status"] == "IN_PROGRESS"
    assert res["phone_number"] == "+919999999999"
    assert "greeting" in res


# 2. Mock conversation turn
@pytest.mark.asyncio
async def test_mock_conversation_turn(db_session):
    voice_svc = MockVoiceService()
    start_res = await voice_svc.start_call(phone_number="+919999999999")
    call_id = start_res["call_id"]

    turn_res = await voice_svc.process_user_message(call_id=call_id, message="I need an e-commerce website for my clothing shop.")
    assert turn_res["call_id"] == call_id
    assert "agent_response" in turn_res
    assert turn_res["classification"] in ["COLD", "WARM", "HOT"]


# 3. Conversation history tracking
@pytest.mark.asyncio
async def test_conversation_history(db_session):
    voice_svc = MockVoiceService()
    start_res = await voice_svc.start_call(phone_number="+919999999999")
    call_id = start_res["call_id"]

    await voice_svc.process_user_message(call_id, "I sell shoes.")
    await voice_svc.process_user_message(call_id, "About 200 products.")

    conv_svc = ConversationService()
    details = conv_svc.get_call_details(call_id, db=db_session)
    assert len(details["transcripts"]) >= 5  # Greeting + 2 customer turns + 2 agent turns
    speakers = [t["speaker"] for t in details["transcripts"]]
    assert "customer" in speakers
    assert "agent" in speakers


# 4. Lead information extraction
@pytest.mark.asyncio
async def test_lead_info_extraction(db_session):
    voice_svc = MockVoiceService()
    start_res = await voice_svc.start_call(phone_number="+918888888888")
    call_id = start_res["call_id"]

    res = await voice_svc.process_user_message(call_id, "I sell handmade jewellery and have 150 products.")
    analysis = res["lead_analysis"]
    assert analysis["product_count"] == 150 or "150" in str(analysis["product_count"])


# 5. Progressive lead analysis
@pytest.mark.asyncio
async def test_progressive_lead_analysis(db_session):
    voice_svc = MockVoiceService()
    start_res = await voice_svc.start_call(phone_number="+917777777777")
    call_id = start_res["call_id"]

    # Turn 1: Initial vague inquiry (COLD)
    t1 = await voice_svc.process_user_message(call_id, "I am just exploring website options.")
    assert t1["classification"] == "COLD"

    # Turn 2: Products count
    t2 = await voice_svc.process_user_message(call_id, "I have around 300 products.")
    assert t2["lead_analysis"]["product_count"] == 300

    # Turn 3: Budget and timeline -> HOT
    t3 = await voice_svc.process_user_message(call_id, "My budget is one lakh and I need it within one month.")
    assert t3["classification"] == "HOT"


# 6. Multilingual language handling
@pytest.mark.asyncio
async def test_language_handling_multilingual(db_session):
    voice_svc = MockVoiceService()
    
    # Telugu turn
    start_res_te = await voice_svc.start_call(phone_number="+916666666666", language="Telugu")
    turn_te = await voice_svc.process_user_message(start_res_te["call_id"], "Naaku oka ecommerce website kavali.")
    assert turn_te["language"] == "Telugu"

    # Hindi turn
    start_res_hi = await voice_svc.start_call(phone_number="+915555555555", language="Hindi")
    turn_hi = await voice_svc.process_user_message(start_res_hi["call_id"], "Mujhe clothing website chahiye.")
    assert turn_hi["language"] == "Hindi"


# 7. HOT classification during conversation
@pytest.mark.asyncio
async def test_hot_classification_during_conversation(db_session):
    voice_svc = MockVoiceService()
    start_res = await voice_svc.start_call(phone_number="+914444444444")
    call_id = start_res["call_id"]

    turn = await voice_svc.process_user_message(
        call_id,
        "I need an e-commerce website for 200 products. My budget is around one lakh and I need it within one month."
    )
    assert turn["classification"] == "HOT"


# 8. WARM classification
@pytest.mark.asyncio
async def test_warm_classification(db_session):
    voice_svc = MockVoiceService()
    start_res = await voice_svc.start_call(phone_number="+913333333333")
    call_id = start_res["call_id"]

    turn = await voice_svc.process_user_message(
        call_id,
        "I want to discuss the budget with my business partner. Call me tomorrow morning."
    )
    assert turn["classification"] == "WARM"


# 9. COLD classification
@pytest.mark.asyncio
async def test_cold_classification(db_session):
    voice_svc = MockVoiceService()
    start_res = await voice_svc.start_call(phone_number="+912222222222")
    call_id = start_res["call_id"]

    turn = await voice_svc.process_user_message(call_id, "I'm just checking what kind of websites you build.")
    assert turn["classification"] == "COLD"


# 10. HOT action triggering
@pytest.mark.asyncio
async def test_hot_action_triggering(db_session):
    voice_svc = MockVoiceService()
    start_res = await voice_svc.start_call(phone_number="+911111111111")
    call_id = start_res["call_id"]

    turn = await voice_svc.process_user_message(
        call_id,
        "I need an e-commerce website for 200 products. My budget is around one lakh and I need it within one month."
    )
    assert turn["classification"] == "HOT"
    assert turn["action_triggered"] == "HOT_LEAD_ALERT"

    # Verify event stored in DB
    event = db_session.query(WhatsAppEvent).filter(WhatsAppEvent.call_id == call_id).first()
    assert event is not None
    assert event.event_type == "HOT_LEAD_ALERT"


# 11. Callback request handling
@pytest.mark.asyncio
async def test_callback_request_handling(db_session):
    voice_svc = MockVoiceService()
    start_res = await voice_svc.start_call(phone_number="+919000000000")
    call_id = start_res["call_id"]

    await voice_svc.process_user_message(call_id, "Call me tomorrow morning.")
    
    cb = db_session.query(ScheduledCallback).filter(ScheduledCallback.call_id == call_id).first()
    assert cb is not None
    assert cb.status == "SCHEDULED"
    assert cb.original_expression == "tomorrow morning"


# 12. Call completion
@pytest.mark.asyncio
async def test_call_completion(db_session):
    voice_svc = MockVoiceService()
    start_res = await voice_svc.start_call(phone_number="+919111111111")
    call_id = start_res["call_id"]

    await voice_svc.process_user_message(call_id, "Thanks for the info.")
    end_res = await voice_svc.end_call(call_id)
    assert end_res["status"] == "COMPLETED"
    assert end_res["call_id"] == call_id


# 13. Missing input validation
def test_missing_input_validation():
    response = client.post(
        "/api/voice/mock/message",
        json={"call_id": "non_existent_call", "message": ""}
    )
    assert response.status_code == 400


# 14. Invalid call ID handling
def test_invalid_call_id():
    response = client.post(
        "/api/voice/mock/message",
        json={"call_id": "invalid_call_99999", "message": "Hello"}
    )
    assert response.status_code == 404


# 15. Voice Factory and Mock mode behavior
def test_mock_mode_voice_behavior():
    vf_mock = VoiceFactory.get_voice_service("mock")
    assert isinstance(vf_mock, MockVoiceService)

    vf_retell = VoiceFactory.get_voice_service("retell")
    assert isinstance(vf_retell, RetellVoiceService)


# 16. API Endpoints Integration Test (Demo Conversation Flow)
def test_demo_conversation_api_flow(db_session):
    # 1. Start Call
    resp_start = client.post(
        "/api/voice/mock/start",
        json={"phone_number": "9353352276", "customer_name": "Surya"}
    )
    assert resp_start.status_code == 200
    call_id = resp_start.json()["call_id"]

    # 2. Turn 1: "I need an ecommerce website."
    t1 = client.post("/api/voice/mock/message", json={"call_id": call_id, "message": "I need an ecommerce website."})
    assert t1.status_code == 200

    # 3. Turn 2: "I sell clothing."
    t2 = client.post("/api/voice/mock/message", json={"call_id": call_id, "message": "I sell clothing."})
    assert t2.status_code == 200

    # 4. Turn 3: "About 500."
    t3 = client.post("/api/voice/mock/message", json={"call_id": call_id, "message": "About 500."})
    assert t3.status_code == 200

    # 5. Turn 4: "Around one lakh."
    t4 = client.post("/api/voice/mock/message", json={"call_id": call_id, "message": "Around one lakh."})
    assert t4.status_code == 200

    # 6. Turn 5: "Within a month." -> triggers HOT
    t5 = client.post("/api/voice/mock/message", json={"call_id": call_id, "message": "Within a month."})
    assert t5.status_code == 200
    data5 = t5.json()
    assert data5["classification"] == "HOT"

    # 7. Get Call Details
    resp_details = client.get(f"/api/voice/calls/{call_id}")
    assert resp_details.status_code == 200
    details = resp_details.json()
    assert details["lead"]["classification"] == "HOT"

    # 8. End Call
    resp_end = client.post("/api/voice/mock/end", json={"call_id": call_id})
    assert resp_end.status_code == 200
    assert resp_end.json()["status"] == "COMPLETED"
