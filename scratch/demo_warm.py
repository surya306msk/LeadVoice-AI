"""
LeadVoice AI — Phase 7 WARM Lead Demo Script
Demonstrates a WARM lead voice conversation with barrier detection, natural language callback
expression parsing ("Call me tomorrow morning"), callback scheduling via APScheduler, and barrier storage.
"""

import asyncio
import sys
import os

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.database import init_db, SessionLocal
from app.models.database_models import ScheduledCallback, Lead, Call, TranscriptLine, WhatsAppEvent
from app.services.voice.mock_voice_service import MockVoiceService

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

async def run_warm_demo():
    print("==================================================")
    print("     LEADVOICE AI — WARM LEAD DEMO SIMULATION    ")
    print("==================================================")
    reset_db()
    voice_svc = MockVoiceService()

    customer_name = "Surya"
    phone_number = "9353352276"

    # Step 1: Start call
    print(f"\n[1] Starting Call for {customer_name} ({phone_number})...")
    start_res = await voice_svc.start_call(phone_number=phone_number, customer_name=customer_name)
    call_id = start_res["call_id"]
    print(f"    Call ID: {call_id}")
    print(f"    Agent Greeting: \"{start_res['greeting']}\"")

    # Step 2: Turn 1 - Discovery & barrier
    user_msg_1 = "I am interested in setting up an e-commerce website for my footwear store, but I need to check our quarterly budget with my business partner."
    print(f"\n[2] User Turn 1: \"{user_msg_1}\"")
    res_1 = await voice_svc.process_user_message(call_id, user_msg_1)
    print(f"    Agent Response: \"{res_1['agent_response']}\"")
    print(f"    Classification: {res_1.get('classification')}")
    print(f"    Extracted Intelligence: {res_1.get('lead_analysis')}")

    # Step 3: Turn 2 - Natural Callback Expression
    user_msg_2 = "Please call me tomorrow morning so we can discuss the proposal together."
    print(f"\n[3] User Turn 2: \"{user_msg_2}\"")
    res_2 = await voice_svc.process_user_message(call_id, user_msg_2)
    print(f"    Agent Response: \"{res_2['agent_response']}\"")
    print(f"    Classification: {res_2.get('classification')}")
    print(f"    Extracted Intelligence: {res_2.get('lead_analysis')}")

    # Step 4: Verify Database Callback Record
    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.phone_number == phone_number).order_by(Lead.id.desc()).first()
        callbacks = db.query(ScheduledCallback).filter(ScheduledCallback.lead_id == lead.id).all() if lead else []
        print(f"\n[4] Database Verification:")
        print(f"    Lead ID: {lead.id if lead else 'N/A'}")
        print(f"    Stored Barrier: {lead.objections_or_barriers if lead else 'N/A'}")
        print(f"    Scheduled Callbacks Count: {len(callbacks)}")
        for cb in callbacks:
            print(f"      - Callback #{cb.id}: Expression='{cb.original_expression}' | Scheduled At='{cb.scheduled_at}' | Status='{cb.status}'")
    finally:
        db.close()

    # Step 5: End call
    print(f"\n[5] Ending Call...")
    end_res = await voice_svc.end_call(call_id)
    print(f"    Final Call Status: {end_res['status']}")

    print("\n==================================================")
    print("        WARM LEAD DEMO COMPLETED SUCCESSFULLY    ")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_warm_demo())
