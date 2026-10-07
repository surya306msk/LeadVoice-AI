import logging
from typing import Optional
from app.services.voice.base_voice_service import BaseVoiceService
from app.services.voice.mock_voice_service import MockVoiceService
from app.services.voice.retell_voice_service import RetellVoiceService
from app.core.config import settings

logger = logging.getLogger("leadvoice.voice.factory")

class VoiceFactory:
    """
    Factory for instantiating the active voice service provider (Mock or Retell).
    """

    @staticmethod
    def get_voice_service(provider_override: Optional[str] = None) -> BaseVoiceService:
        provider = (provider_override or settings.VOICE_PROVIDER or "mock").lower().strip()

        if provider == "retell":
            return RetellVoiceService()
        elif provider == "mock":
            return MockVoiceService()
        else:
            logger.warning(f"Unknown voice provider '{provider}'. Defaulting to MockVoiceService.")
            return MockVoiceService()
