import pytest
import pytz
from datetime import datetime
from fastapi.testclient import TestClient
from app.main import app
from app.database.database import SessionLocal
from app.models.database_models import Lead, ScheduledCallback
from app.services.callback_parser_service import CallbackParserService

client = TestClient(app)
tz = pytz.timezone("Asia/Kolkata")
FIXED_REF = tz.localize(datetime(2026, 8, 28, 12, 0, 0))

# Setup a lead for testing DB scheduling
@pytest.fixture(scope="module")
def setup_lead():
    db = SessionLocal()
    # clean tables
    db.query(ScheduledCallback).delete()
    db.query(Lead).delete()
    db.commit()

    lead = Lead(customer_name="Test User", phone_number="1234567890", lead_classification="WARM")
    db.add(lead)
    db.commit()
    db.refresh(lead)
    yield lead.id
    db.close()

@pytest.mark.asyncio
async def test_callback_parser_tomorrow_morning():
    parser = CallbackParserService()
    res = await parser.parse_callback("Call me tomorrow morning.", reference_time=FIXED_REF)
    assert res.callback_requested is True
    assert res.scheduled_at == tz.localize(datetime(2026, 8, 29, 10, 0, 0))

@pytest.mark.asyncio
async def test_callback_parser_tomorrow_evening():
    parser = CallbackParserService()
    res = await parser.parse_callback("Call me tomorrow evening.", reference_time=FIXED_REF)
    assert res.callback_requested is True
    assert res.scheduled_at == tz.localize(datetime(2026, 8, 29, 18, 0, 0))

@pytest.mark.asyncio
async def test_callback_parser_in_two_days():
    parser = CallbackParserService()
    res = await parser.parse_callback("Call me in two days.", reference_time=FIXED_REF)
    assert res.callback_requested is True
    assert res.scheduled_at == tz.localize(datetime(2026, 8, 30, 10, 0, 0))

@pytest.mark.asyncio
async def test_callback_parser_at_6_pm():
    parser = CallbackParserService()
    res = await parser.parse_callback("Call me at 6 PM.", reference_time=FIXED_REF)
    assert res.callback_requested is True
    assert res.scheduled_at == tz.localize(datetime(2026, 8, 28, 18, 0, 0))

@pytest.mark.asyncio
async def test_callback_parser_at_10_am():
    parser = CallbackParserService()
    res = await parser.parse_callback("Call me at 10 AM.", reference_time=FIXED_REF)
    assert res.callback_requested is True
    # 10 AM is in the past relative to 12:00 PM ref time, should schedule tomorrow
    assert res.scheduled_at == tz.localize(datetime(2026, 8, 29, 10, 0, 0))

@pytest.mark.asyncio
async def test_callback_parser_next_monday_morning():
    parser = CallbackParserService()
    res = await parser.parse_callback("Call me next Monday morning.", reference_time=FIXED_REF)
    assert res.callback_requested is True
    # Reference Aug 28, 2026 is a Friday. Next Monday is Aug 31, 2026.
    assert res.scheduled_at == tz.localize(datetime(2026, 8, 31, 10, 0, 0))

@pytest.mark.asyncio
async def test_callback_parser_this_friday_afternoon():
    parser = CallbackParserService()
    res = await parser.parse_callback("Call me this Friday afternoon.", reference_time=FIXED_REF)
    assert res.callback_requested is True
    # Friday afternoon is today, Aug 28, 2026 at 3:00 PM (15:00)
    assert res.scheduled_at == tz.localize(datetime(2026, 8, 28, 15, 0, 0))

@pytest.mark.asyncio
async def test_callback_parser_sometime_later():
    parser = CallbackParserService()
    res = await parser.parse_callback("Call me sometime later.", reference_time=FIXED_REF)
    assert res.callback_requested is True
    assert res.scheduled_at is None

def test_api_duplicate_prevention(setup_lead):
    lead_id = setup_lead
    # Schedule first callback
    resp1 = client.post(
        "/api/callbacks/schedule",
        json={"lead_id": lead_id, "callback_expression": "Call me tomorrow morning"}
    )
    assert resp1.status_code == 200
    cb1 = resp1.json()

    # Schedule second callback (should cancel cb1)
    resp2 = client.post(
        "/api/callbacks/schedule",
        json={"lead_id": lead_id, "callback_expression": "Call me tomorrow evening"}
    )
    assert resp2.status_code == 200
    cb2 = resp2.json()

    # Check cb1 is CANCELLED in DB
    resp_cb1 = client.get(f"/api/callbacks/{cb1['callback_id']}")
    assert resp_cb1.status_code == 200
    assert resp_cb1.json()["status"] == "CANCELLED"
    
    # Check cb2 is SCHEDULED in DB
    assert cb2["status"] == "SCHEDULED"

def test_api_cancellation(setup_lead):
    lead_id = setup_lead
    # Schedule
    resp = client.post(
        "/api/callbacks/schedule",
        json={"lead_id": lead_id, "callback_expression": "Call me in 3 days"}
    )
    assert resp.status_code == 200
    cb = resp.json()
    assert cb["status"] == "SCHEDULED"

    # Cancel
    resp_del = client.delete(f"/api/callbacks/{cb['callback_id']}")
    assert resp_del.status_code == 200
    assert resp_del.json()["status"] == "CANCELLED"
