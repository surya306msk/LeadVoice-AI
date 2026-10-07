import logging
from typing import Optional, Dict, Any
from app.services.voice.base_voice_service import BaseVoiceService
from app.services.conversation_service import ConversationService

logger = logging.getLogger("leadvoice.voice.mock")

class MockVoiceService(BaseVoiceService):
    """
    Local Mock Voice Service for development and testing without paid telephony APIs.
    Communicates with ConversationService for state, natural responses, progressive lead intelligence,
    and real-time Phase 4 action execution.
    """

    def __init__(self):
        self.conv_service = ConversationService()

    async def start_call(self, phone_number: str, customer_name: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        logger.info(f"[MOCK VOICE] Starting call for phone={phone_number}")
        res = await self.conv_service.start_call(
            phone_number=phone_number,
            customer_name=customer_name,
            language=kwargs.get("language")
        )
        return res

    async def process_user_message(self, call_id: str, message: str, **kwargs) -> Dict[str, Any]:
        logger.info(f"[MOCK VOICE] Turn for call_id={call_id}: '{message[:50]}'")
        res = await self.conv_service.process_user_turn(
            call_id=call_id,
            user_message=message
        )
        return res

    async def generate_agent_response(self, call_id: str, message: str, **kwargs) -> Dict[str, Any]:
        res = await self.process_user_message(call_id, message, **kwargs)
        return {
            "call_id": call_id,
            "agent_response": res.get("agent_response", ""),
            "language": res.get("language", "English")
        }

    async def end_call(self, call_id: str, **kwargs) -> Dict[str, Any]:
        logger.info(f"[MOCK VOICE] Ending call for call_id={call_id}")
        res = await self.conv_service.end_call(call_id=call_id)
        return res
