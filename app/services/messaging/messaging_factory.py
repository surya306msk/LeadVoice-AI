import logging
import uuid
from typing import Optional, Dict, Any
from app.services.messaging.base_messaging_service import BaseMessagingService
from app.services.messaging.telegram_service import TelegramService
from app.services.messaging.whatsapp_service import WhatsAppService
from app.core.config import settings

logger = logging.getLogger("leadvoice.messaging.factory")

class MockMessagingService(BaseMessagingService):
    """
    Pure mock messaging provider for testing/development.
    """

    async def send_message(self, recipient: str, text: str, **kwargs) -> Dict[str, Any]:
        logger.info(f"[PURE MOCK SERVICE] send_message to {recipient}: {text[:50]}...")
        return {
            "success": True,
            "provider": "mock",
            "provider_message_id": f"mock_msg_{uuid.uuid4().hex[:8]}",
            "error": None
        }

    async def send_document(self, recipient: str, document_path: str, caption: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        logger.info(f"[PURE MOCK SERVICE] send_document to {recipient}: {document_path}")
        return {
            "success": True,
            "provider": "mock",
            "provider_message_id": f"mock_doc_{uuid.uuid4().hex[:8]}",
            "error": None
        }

    async def send_image(self, recipient: str, image_path: str, caption: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        logger.info(f"[PURE MOCK SERVICE] send_image to {recipient}: {image_path}")
        return {
            "success": True,
            "provider": "mock",
            "provider_message_id": f"mock_img_{uuid.uuid4().hex[:8]}",
            "error": None
        }


class MessagingFactory:
    """
    Factory class to instantiate and provide messaging service implementation.
    """

    @staticmethod
    def get_messaging_service(provider_override: Optional[str] = None) -> BaseMessagingService:
        provider = (provider_override or settings.MESSAGING_PROVIDER or "telegram").lower().strip()

        if provider == "telegram":
            return TelegramService()
        elif provider == "whatsapp":
            return WhatsAppService()
        elif provider == "mock":
            return MockMessagingService()
        else:
            logger.warning(f"Unknown messaging provider '{provider}'. Defaulting to TelegramService.")
            return TelegramService()
