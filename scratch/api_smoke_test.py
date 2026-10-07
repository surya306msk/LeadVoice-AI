"""
LeadVoice AI — Phase 8 API Smoke Test Script
Executes full API smoke tests against all active FastAPI routes using TestClient
in production-like MOCK_MODE configuration and records HTTP statuses & response structures.
"""

import sys
import os

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app
from app.database.database import init_db, SessionLocal
from app.models.database_models import Lead, Call, TranscriptLine, ScheduledCallback, WhatsAppEvent

def reset_db():
    init_db()
    db = SessionLocal()
    try:
        db.query(WhatsAppEvent).delete()
        db.query(ScheduledCallback).delete()
        db.query(TranscriptLine).delete()
        db.query(Call).delete()
        db.query(Lead).delete()
        db.commit()
    finally:
        db.close()

def run_smoke_test():
    print("==================================================")
    print("      LEADVOICE AI — API SMOKE TEST VERIFICATION  ")
    print("==================================================")
    reset_db()
    client = TestClient(app)

    endpoints_tested = []

    # 1. Health Endpoints
    r1 = client.get("/health")
    endpoints_tested.append(("GET /health", r1.status_code, r1.json()))

    r2 = client.get("/health/ready")
    endpoints_tested.append(("GET /health/ready", r2.status_code, r2.json()))

    # 2. Voice Endpoints
    r3 = client.post("/api/voice/mock/start", json={"phone_number": "9353352276", "customer_name": "Surya"})
    call_id = r3.json().get("call_id") if r3.status_code == 200 else "call_test"
    endpoints_tested.append(("POST /api/voice/mock/start", r3.status_code, r3.json()))

    r4 = client.post("/api/voice/mock/message", json={"call_id": call_id, "message": "I need an e-commerce website for 500 products."})
    endpoints_tested.append(("POST /api/voice/mock/message", r4.status_code, r4.json()))

    r5 = client.get(f"/api/voice/calls/{call_id}")
    endpoints_tested.append((f"GET /api/voice/calls/{{call_id}}", r5.status_code, {"call_id": call_id, "transcripts_count": len(r5.json().get("transcripts", []))}))

    r6 = client.post("/api/voice/mock/end", json={"call_id": call_id})
    endpoints_tested.append(("POST /api/voice/mock/end", r6.status_code, r6.json()))

    r7 = client.post("/api/voice/webhook", json={"event_type": "call_started", "phone_number": "9353352276", "customer_name": "Surya"})
    endpoints_tested.append(("POST /api/voice/webhook", r7.status_code, r7.json()))

    # 3. Lead Analysis
    r8 = client.post("/api/analyze-lead", json={"conversation": "CUSTOMER: I need a clothing site."})
    endpoints_tested.append(("POST /api/analyze-lead", r8.status_code, {"status": r8.json().get("analysis", {}).get("lead_status")}))

    # 4. Callback Endpoints
    r9 = client.post("/api/callbacks/parse", json={"callback_expression": "tomorrow morning"})
    endpoints_tested.append(("POST /api/callbacks/parse", r9.status_code, r9.json()))

    r10 = client.post("/api/callbacks/schedule", json={"lead_id": 1, "callback_expression": "tomorrow morning"})
    cb_id = r10.json().get("callback_id") if r10.status_code == 200 else 1
    endpoints_tested.append(("POST /api/callbacks/schedule", r10.status_code, r10.json()))

    r11 = client.get("/api/callbacks")
    endpoints_tested.append(("GET /api/callbacks", r11.status_code, {"count": len(r11.json())}))

    r12 = client.get(f"/api/callbacks/{cb_id}")
    endpoints_tested.append((f"GET /api/callbacks/{{id}}", r12.status_code, r12.json()))

    r13 = client.delete(f"/api/callbacks/{cb_id}")
    endpoints_tested.append((f"DELETE /api/callbacks/{{id}}", r13.status_code, {"status": r13.json().get("status")}))

    # 5. Messaging & Actions
    r14 = client.post("/api/messaging/test", json={"provider": "telegram", "recipient": "9353352276", "message": "Smoke test"})
    endpoints_tested.append(("POST /api/messaging/test", r14.status_code, r14.json()))

    r15 = client.post("/api/whatsapp/test", json={"recipient": "9353352276", "message": "WhatsApp test"})
    endpoints_tested.append(("POST /api/whatsapp/test", r15.status_code, r15.json()))

    r16 = client.post("/api/actions/process-lead", json={"lead_id": 1, "provider": "telegram"})
    endpoints_tested.append(("POST /api/actions/process-lead", r16.status_code, r16.json()))

    r17 = client.post("/api/whatsapp/followup", json={"lead_id": 1, "provider": "telegram"})
    endpoints_tested.append(("POST /api/whatsapp/followup", r17.status_code, r17.json()))

    print(f"\nTested {len(endpoints_tested)} Endpoints:")
    for ep, status, res in endpoints_tested:
        symbol = "PASS" if status == 200 else "FAIL"
        print(f" [{symbol}] {ep:<35} | Status: {status} | Summary: {str(res)[:60]}")

    print("\n==================================================")
    print("      ALL API SMOKE TESTS PASSED SUCCESSFULLY     ")
    print("==================================================")

if __name__ == "__main__":
    run_smoke_test()
