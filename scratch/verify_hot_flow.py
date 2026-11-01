import asyncio, sys, pathlib
# Add project root to sys.path for package imports
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from app.services.llm_service import LLMService
from app.services.action_service import ActionService
from app.services.conversation_service import ConversationService
from app.services.lead_service import LeadService
from app.core.config import settings

async def main():
    # Ensure mock mode
    settings.MOCK_MODE = True
    conversation = "I need an online store.\nAbout 500 products.\nMy budget is around 1 lakh.\nWe need it in 3 weeks.\nI'm the founder."
    llm = LLMService()
    analysis = await llm.analyze_conversation(conversation)
    print("[ANALYSIS]")
    print(analysis)
    # Create lead in DB
    lead_svc = LeadService()
    lead = await lead_svc.create_lead(name='Surya', phone_number='9353352276', business_type=analysis.business_type)
    # Process conversation (which will trigger action if HOT)
    conv_svc = ConversationService()
    result = await conv_svc.process_user_turn(conversation=conversation, lead_id=lead.id)
    print("[CONVERSATION RESULT]")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
