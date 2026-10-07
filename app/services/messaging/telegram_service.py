import os
import httpx
import logging
import uuid
from typing import Optional, Dict, Any
from app.services.messaging.base_messaging_service import BaseMessagingService
from app.core.config import settings
from app.core.logging import mask_phone

logger = logging.getLogger("leadvoice.messaging.telegram")

class TelegramService(BaseMessagingService):
    """
    Telegram Bot API integration implementing BaseMessagingService.
    Supports MOCK_MODE for local testing without Telegram credentials.
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        mock_mode: Optional[bool] = None
    ):
        self.bot_token = bot_token if bot_token is not None else settings.TELEGRAM_BOT_TOKEN
        self.default_chat_id = chat_id if chat_id is not None else settings.TELEGRAM_CHAT_ID
        self.mock_mode = mock_mode if mock_mode is not None else settings.MOCK_MODE
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def _resolve_chat_id(self, recipient: Optional[str]) -> Optional[str]:
        if recipient and recipient.strip():
            return recipient.strip()
        if self.default_chat_id and self.default_chat_id.strip():
            return self.default_chat_id.strip()
        return None

    async def send_message(self, recipient: str, text: str, **kwargs) -> Dict[str, Any]:
        target_chat_id = self._resolve_chat_id(recipient)
        if not target_chat_id and not self.mock_mode:
            logger.error("Telegram error: Missing chat ID / recipient")
            return {
                "success": False,
                "provider": "telegram",
                "provider_message_id": None,
                "error": "Missing recipient / Telegram chat ID"
            }

        if self.mock_mode or not self.bot_token:
            masked_id = mask_phone(target_chat_id) if target_chat_id else 'mock_chat'
            logger.info(f"[MOCK TELEGRAM] Sending message to {masked_id}: {text[:50]}...")
            return {
                "success": True,
                "provider": "telegram",
                "provider_message_id": f"mock_tg_msg_{uuid.uuid4().hex[:8]}",
                "error": None
            }

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": target_chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    res_json = resp.json()
                    msg_id = str(res_json.get("result", {}).get("message_id", ""))
                    return {
                        "success": True,
                        "provider": "telegram",
                        "provider_message_id": msg_id,
                        "error": None
                    }
                else:
                    err_msg = f"Telegram API error HTTP {resp.status_code}: {resp.text}"
                    logger.error(err_msg)
                    return {
                        "success": False,
                        "provider": "telegram",
                        "provider_message_id": None,
                        "error": err_msg
                    }
        except Exception as e:
            logger.error(f"Telegram request failed: {e}")
            return {
                "success": False,
                "provider": "telegram",
                "provider_message_id": None,
                "error": str(e)
            }

    async def send_document(self, recipient: str, document_path: str, caption: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        target_chat_id = self._resolve_chat_id(recipient)
        if not target_chat_id and not self.mock_mode:
            return {
                "success": False,
                "provider": "telegram",
                "provider_message_id": None,
                "error": "Missing recipient / Telegram chat ID"
            }

        if self.mock_mode or not self.bot_token:
            logger.info(f"[MOCK TELEGRAM] Sending document '{document_path}' to {target_chat_id or 'mock_chat'}")
            return {
                "success": True,
                "provider": "telegram",
                "provider_message_id": f"mock_tg_doc_{uuid.uuid4().hex[:8]}",
                "error": None
            }

        if not os.path.exists(document_path):
            err_msg = f"Document file not found: {document_path}"
            logger.error(err_msg)
            return {
                "success": False,
                "provider": "telegram",
                "provider_message_id": None,
                "error": err_msg
            }

        url = f"{self.base_url}/sendDocument"
        data = {"chat_id": target_chat_id}
        if caption:
            data["caption"] = caption

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                with open(document_path, "rb") as f:
                    files = {"document": f}
                    resp = await client.post(url, data=data, files=files)
                if resp.status_code == 200:
                    res_json = resp.json()
                    msg_id = str(res_json.get("result", {}).get("message_id", ""))
                    return {
                        "success": True,
                        "provider": "telegram",
                        "provider_message_id": msg_id,
                        "error": None
                    }
                else:
                    err_msg = f"Telegram document send error HTTP {resp.status_code}: {resp.text}"
                    logger.error(err_msg)
                    return {
                        "success": False,
                        "provider": "telegram",
                        "provider_message_id": None,
                        "error": err_msg
                    }
        except Exception as e:
            logger.error(f"Telegram document request failed: {e}")
            return {
                "success": False,
                "provider": "telegram",
                "provider_message_id": None,
                "error": str(e)
            }

    async def send_image(self, recipient: str, image_path: str, caption: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        target_chat_id = self._resolve_chat_id(recipient)
        if not target_chat_id and not self.mock_mode:
            return {
                "success": False,
                "provider": "telegram",
                "provider_message_id": None,
                "error": "Missing recipient / Telegram chat ID"
            }

        if self.mock_mode or not self.bot_token:
            logger.info(f"[MOCK TELEGRAM] Sending image '{image_path}' to {target_chat_id or 'mock_chat'}")
            return {
                "success": True,
                "provider": "telegram",
                "provider_message_id": f"mock_tg_img_{uuid.uuid4().hex[:8]}",
                "error": None
            }

        if not os.path.exists(image_path):
            err_msg = f"Image file not found: {image_path}"
            logger.error(err_msg)
            return {
                "success": False,
                "provider": "telegram",
                "provider_message_id": None,
                "error": err_msg
            }

        url = f"{self.base_url}/sendPhoto"
        data = {"chat_id": target_chat_id}
        if caption:
            data["caption"] = caption

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                with open(image_path, "rb") as f:
                    files = {"photo": f}
                    resp = await client.post(url, data=data, files=files)
                if resp.status_code == 200:
                    res_json = resp.json()
                    msg_id = str(res_json.get("result", {}).get("message_id", ""))
                    return {
                        "success": True,
                        "provider": "telegram",
                        "provider_message_id": msg_id,
                        "error": None
                    }
                else:
                    err_msg = f"Telegram photo send error HTTP {resp.status_code}: {resp.text}"
                    logger.error(err_msg)
                    return {
                        "success": False,
                        "provider": "telegram",
                        "provider_message_id": None,
                        "error": err_msg
                    }
        except Exception as e:
            logger.error(f"Telegram image request failed: {e}")
            return {
                "success": False,
                "provider": "telegram",
                "provider_message_id": None,
                "error": str(e)
            }
