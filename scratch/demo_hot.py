"""HOT lead demo: e-commerce inquiry → budget/timeline → HOT classification → mock alert."""

import asyncio
import sys
import os

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.database import init_db, SessionLocal
from app.models.database_models import Lead, Call, TranscriptLine, ScheduledCallback, WhatsAppEvent
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

async def run_hot_demo():
    print("==================================================")
    print("      LEADVOICE AI — HOT LEAD DEMO SIMULATION     ")
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

    # Step 2: Turn 1 - Discovery
    user_msg_1 = "I need a high-converting e-commerce website for my clothing and apparel business with around 500 catalog items."
    print(f"\n[2] User Turn 1: \"{user_msg_1}\"")
    res_1 = await voice_svc.process_user_message(call_id, user_msg_1)
    print(f"    Agent Response: \"{res_1['agent_response']}\"")
    print(f"    Detected Language: {res_1.get('language', 'English')}")
    print(f"    Classification: {res_1.get('classification')}")
    print(f"    Extracted Intelligence: {res_1.get('lead_analysis')}")

    # Step 3: Turn 2 - Budget & Timeline
    user_msg_2 = "My budget is around 1 lakh rupees and I need the project completed within 3 weeks."
    print(f"\n[3] User Turn 2: \"{user_msg_2}\"")
    res_2 = await voice_svc.process_user_message(call_id, user_msg_2)
    print(f"    Agent Response: \"{res_2['agent_response']}\"")
    print(f"    Classification: {res_2.get('classification')}")
    print(f"    Extracted Intelligence: {res_2.get('lead_analysis')}")

    # Step 4: Turn 3 - Decision Maker & HOT Trigger
    user_msg_3 = "I am the founder and sole decision maker for this project."
    print(f"\n[4] User Turn 3: \"{user_msg_3}\"")
    res_3 = await voice_svc.process_user_message(call_id, user_msg_3)
    print(f"    Agent Response: \"{res_3['agent_response']}\"")
    print(f"    Classification: {res_3.get('classification')}")
    print(f"    Action Executed: {res_3.get('action_triggered')}")
    print(f"    Extracted Intelligence: {res_3.get('lead_analysis')}")

    # Step 5: End call
    print(f"\n[5] Ending Call...")
    end_res = await voice_svc.end_call(call_id)
    print(f"    Final Call Status: {end_res['status']}")

    print("\n==================================================")
    print("         HOT LEAD DEMO COMPLETED SUCCESSFULLY     ")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_hot_demo())
