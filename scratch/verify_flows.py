import asyncio, sys, pathlib
# Set up import path
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app
from app.services.conversation_service import ConversationService

from app.core.config import settings

client = TestClient(app)

async def verify_flow(name, phone, convo, expected):
    # Analyze via API
    resp = client.post("/api/analyze-lead", json={"conversation": convo})
    assert resp.status_code == 200, f"API error: {resp.status_code}"
    analysis = resp.json()["analysis"]
    for k, v in expected.items():
        assert analysis.get(k) == v, f"{k} expected {v}, got {analysis.get(k)}"
    print(f"[{name}] Analysis OK")
    # Start call (creates lead if needed)
    conv_svc = ConversationService()
    start_res = await conv_svc.start_call(phone_number=phone, customer_name=name)
    call_id = start_res["call_id"]
    # Process conversation (triggers action)
    result = await conv_svc.process_user_turn(call_id=call_id, user_message=convo)
    print(f"[{name}] Conversation result: {result}\n")

async def main():
    settings.MOCK_MODE = True
    hot_convo = "I need an online store.\nAbout 500 products.\nMy budget is around 1 lakh.\nWe need it in 3 weeks.\nI'm the founder."
    await verify_flow(
        name="Surya",
        phone="9353352276",
        convo=hot_convo,
        expected={
            "product_count": 500,
            "budget": "100000 INR",
            "timeline": "3 weeks",
            "decision_maker": "Founder",
            "lead_status": "HOT",
            "recommended_action": "SEND_WHATSAPP_NOW",
        },
    )
    # Warm flow
    warm_convo = "I want an e-commerce site but need to discuss budget with my partner. Call me tomorrow morning."
    await verify_flow(
        name="WarmUser",
        phone="1234567890",
        convo=warm_convo,
        expected={"lead_status": "WARM"},
    )
    # Cold flow
    cold_convo = "Just checking what you build. No immediate plans."
    await verify_flow(
        name="ColdUser",
        phone="0987654321",
        convo=cold_convo,
        expected={"lead_status": "COLD"},
    )

if __name__ == "__main__":
    asyncio.run(main())
