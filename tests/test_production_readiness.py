import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.logging import mask_secret, mask_phone
from app.core.config import settings

client = TestClient(app)

# 1. Health check
def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

# 2. Health readiness check
def test_health_readiness_endpoint():
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
    assert "mock_mode" in data

# 3. Privacy masking helpers
def test_privacy_masking_helpers():
    assert mask_secret("") == "[EMPTY]"
    assert mask_secret("short") == "****"
    assert mask_secret("sk-proj-1234567890secret") == "sk-****cret"

    assert mask_phone("") == "[EMPTY]"
    assert mask_phone("123") == "****"
    assert mask_phone("9353352276") == "935****276"
    assert mask_phone("+919353352276") == "+91****276"

# 4. Voice Telephony Webhook - Call Started
def test_voice_webhook_call_started():
    response = client.post(
        "/api/voice/webhook",
        json={
            "event_type": "call_started",
            "phone_number": "9353352276",
            "customer_name": "Surya"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["event"] == "call_started"
    assert "call_id" in data["data"]

# 5. Voice Telephony Webhook - Transcript & Call Ended
def test_voice_webhook_transcript_and_ended():
    # Start
    resp_start = client.post(
        "/api/voice/webhook",
        json={"event_type": "call_started", "phone_number": "9353352276"}
    )
    call_id = resp_start.json()["data"]["call_id"]

    # Transcript turn
    resp_tx = client.post(
        "/api/voice/webhook",
        json={
            "event_type": "transcript",
            "call_id": call_id,
            "message": "I need an ecommerce website for 200 products."
        }
    )
    assert resp_tx.status_code == 200
    assert resp_tx.json()["event"] == "transcript"

    # End
    resp_end = client.post(
        "/api/voice/webhook",
        json={"event_type": "call_ended", "call_id": call_id}
    )
    assert resp_end.status_code == 200
    assert resp_end.json()["event"] == "call_ended"

# 6. Webhook invalid event handling
def test_voice_webhook_invalid_event():
    response = client.post(
        "/api/voice/webhook",
        json={"event_type": "unsupported_event"}
    )
    assert response.status_code == 400

# 7. Clean JSON Exception Error Response
def test_clean_error_response():
    response = client.get("/api/voice/calls/non_existent_call_id_12345")
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert "error" in data
    assert data["code"] == "HTTP_404"
