"""
LeadVoice AI — Phase 7 Multilingual Demo Script
Demonstrates natural multilingual sales conversations in:
- English
- Hindi / Hinglish
- Telugu / Teluglish

Displays input transcript, detected language, extracted lead intelligence, classification,
and natural sales-consultative assistant responses.
"""

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

async def run_multilingual_demo():
    print("==================================================")
    print("   LEADVOICE AI — MULTILINGUAL DEMO SIMULATION    ")
    print("==================================================")
    reset_db()
    voice_svc = MockVoiceService()
    customer_name = "Surya"
    phone_number = "9353352276"

    # Start Call
    print(f"\n[1] Starting Multilingual Call Session for {customer_name} ({phone_number})...")
    start_res = await voice_svc.start_call(phone_number=phone_number, customer_name=customer_name)
    call_id = start_res["call_id"]
    print(f"    Call ID: {call_id}")
    print(f"    Initial Greeting: \"{start_res['greeting']}\"")

    # 1. English Turn
    turn_1 = "Hi, I am looking for a custom e-commerce website for my apparel brand."
    print(f"\n[2] ENGLISH TURN:")
    print(f"    Input Transcript: \"{turn_1}\"")
    res_1 = await voice_svc.process_user_message(call_id, turn_1)
    print(f"    Detected Language: {res_1.get('language')}")
    print(f"    Classification: {res_1.get('classification')}")
    print(f"    Assistant Response: \"{res_1.get('agent_response')}\"")
    print(f"    Lead Intelligence: {res_1.get('lead_analysis')}")

    # 2. Hindi / Hinglish Turn
    turn_2 = "Mere paas lagbhag 500 products hain aur mera budget ek lakh rupaye hai."
    print(f"\n[3] HINDI / HINGLISH TURN:")
    print(f"    Input Transcript: \"{turn_2}\"")
    res_2 = await voice_svc.process_user_message(call_id, turn_2)
    print(f"    Detected Language: {res_2.get('language')}")
    print(f"    Classification: {res_2.get('classification')}")
    print(f"    Assistant Response: \"{res_2.get('agent_response')}\"")
    print(f"    Lead Intelligence: {res_2.get('lead_analysis')}")

    # 3. Telugu / Teluglish Turn
    turn_3 = "Naaku e-commerce website kavali, 1 month lo launch cheyyali."
    print(f"\n[4] TELUGU / TELUGLISH TURN:")
    print(f"    Input Transcript: \"{turn_3}\"")
    res_3 = await voice_svc.process_user_message(call_id, turn_3)
    print(f"    Detected Language: {res_3.get('language')}")
    print(f"    Classification: {res_3.get('classification')}")
    print(f"    Assistant Response: \"{res_3.get('agent_response')}\"")
    print(f"    Lead Intelligence: {res_3.get('lead_analysis')}")

    # End Call
    print(f"\n[5] Ending Call...")
    end_res = await voice_svc.end_call(call_id)
    print(f"    Final Call Status: {end_res['status']}")

    print("\n==================================================")
    print("   MULTILINGUAL DEMO COMPLETED SUCCESSFULLY       ")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_multilingual_demo())
