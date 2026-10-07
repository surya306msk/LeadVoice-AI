import httpx
import logging
from typing import Optional, Dict, Any
from app.services.voice.base_voice_service import BaseVoiceService
from app.services.voice.mock_voice_service import MockVoiceService
from app.core.config import settings

logger = logging.getLogger("leadvoice.voice.retell")

class RetellVoiceService(BaseVoiceService):
    """
    Retell Telephony Provider Integration implementing BaseVoiceService.
    Isolated provider-specific logic. Falls back to MockVoiceService when in MOCK_MODE or missing API keys.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        agent_id: Optional[str] = None,
        mock_mode: Optional[bool] = None
    ):
        self.api_key = api_key if api_key is not None else settings.RETELL_API_KEY
        self.agent_id = agent_id if agent_id is not None else settings.RETELL_AGENT_ID
        self.mock_mode = mock_mode if mock_mode is not None else settings.MOCK_MODE
        self.mock_fallback = MockVoiceService()
        self.base_url = "https://api.retellai.com"

    def _is_mock(self) -> bool:
        if self.mock_mode:
            return True
        if not self.api_key or not self.agent_id or self.api_key.startswith("mock"):
            return True
        return False

    async def start_call(self, phone_number: str, customer_name: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        if self._is_mock():
            logger.info(f"[RETELL VOICE - MOCK FALLBACK] Starting call for phone={phone_number}")
            return await self.mock_fallback.start_call(phone_number, customer_name, **kwargs)

        url = f"{self.base_url}/v2/create-phone-call"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "agent_id": self.agent_id,
            "to_number": phone_number
        }
        if customer_name:
            payload["retell_llm_dynamic_variables"] = {"customer_name": customer_name}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code in [200, 201]:
                    data = resp.json()
                    call_id = data.get("call_id", "")
                    return {
                        "call_id": call_id,
                        "status": "IN_PROGRESS",
                        "provider": "retell",
                        "message": "Retell call initiated successfully"
                    }
                else:
                    logger.error(f"Retell API error HTTP {resp.status_code}: {resp.text}")
                    return await self.mock_fallback.start_call(phone_number, customer_name, **kwargs)
        except Exception as e:
            logger.error(f"Retell request failed: {e}. Falling back to mock voice.")
            return await self.mock_fallback.start_call(phone_number, customer_name, **kwargs)

    async def process_user_message(self, call_id: str, message: str, **kwargs) -> Dict[str, Any]:
        return await self.mock_fallback.process_user_message(call_id, message, **kwargs)

    async def generate_agent_response(self, call_id: str, message: str, **kwargs) -> Dict[str, Any]:
        return await self.mock_fallback.generate_agent_response(call_id, message, **kwargs)

    async def end_call(self, call_id: str, **kwargs) -> Dict[str, Any]:
        return await self.mock_fallback.end_call(call_id, **kwargs)
