from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class BaseMessagingService(ABC):
    """
    Abstract Base Class for Messaging Providers (Telegram, WhatsApp, Mock).
    """

    @abstractmethod
    async def send_message(self, recipient: str, text: str, **kwargs) -> Dict[str, Any]:
        """
        Send a text message to recipient.
        Returns a dict:
        {
            "success": bool,
            "provider": str,
            "provider_message_id": Optional[str],
            "error": Optional[str]
        }
        """
        pass

    @abstractmethod
    async def send_document(self, recipient: str, document_path: str, caption: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Send a document to recipient.
        """
        pass

    @abstractmethod
    async def send_image(self, recipient: str, image_path: str, caption: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Send an image to recipient.
        """
        pass
