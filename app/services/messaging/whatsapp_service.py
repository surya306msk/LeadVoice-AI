import os
import httpx
import logging
import uuid
from typing import Optional, Dict, Any
from app.services.messaging.base_messaging_service import BaseMessagingService
from app.core.config import settings
from app.core.logging import mask_phone

logger = logging.getLogger("leadvoice.messaging.whatsapp")

class WhatsAppService(BaseMessagingService):
    """
    WhatsApp Cloud API integration implementing BaseMessagingService.
    Supports MOCK_MODE for local testing without WhatsApp API credentials.
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        phone_number_id: Optional[str] = None,
        api_version: Optional[str] = None,
        default_recipient: Optional[str] = None,
        mock_mode: Optional[bool] = None
    ):
        self.access_token = access_token if access_token is not None else settings.WHATSAPP_ACCESS_TOKEN
        self.phone_number_id = phone_number_id if phone_number_id is not None else settings.WHATSAPP_PHONE_NUMBER_ID
        self.api_version = api_version if api_version is not None else settings.WHATSAPP_API_VERSION
        self.default_recipient = default_recipient if default_recipient is not None else settings.WHATSAPP_RECIPIENT_PHONE
        self.mock_mode = mock_mode if mock_mode is not None else settings.MOCK_MODE

    def _resolve_recipient(self, recipient: Optional[str]) -> Optional[str]:
        if recipient and recipient.strip():
            return recipient.strip()
        if self.default_recipient and self.default_recipient.strip():
            return self.default_recipient.strip()
        return None

    def _is_mock(self) -> bool:
        if self.mock_mode:
            return True
        if not self.access_token or not self.phone_number_id:
            return True
        return False

    async def send_message(self, recipient: str, text: str, **kwargs) -> Dict[str, Any]:
        target_phone = self._resolve_recipient(recipient)
        if not target_phone and not self.mock_mode:
            logger.error("WhatsApp error: Missing recipient phone number")
            return {
                "success": False,
                "provider": "whatsapp",
                "provider_message_id": None,
                "error": "Missing recipient phone number"
            }

        if self._is_mock():
            masked_phone = mask_phone(target_phone) if target_phone else 'mock_phone'
            logger.info(f"[MOCK WHATSAPP] Sending message to {masked_phone}: {text[:50]}...")
            return {
                "success": True,
                "provider": "whatsapp",
                "provider_message_id": f"mock_wa_msg_{uuid.uuid4().hex[:8]}",
                "error": None
            }

        url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": target_phone,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": text
            }
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code in [200, 201]:
                    res_json = resp.json()
                    msg_id = ""
                    if "messages" in res_json and len(res_json["messages"]) > 0:
                        msg_id = res_json["messages"][0].get("id", "")
                    return {
                        "success": True,
                        "provider": "whatsapp",
                        "provider_message_id": msg_id or f"wa_msg_{uuid.uuid4().hex[:8]}",
                        "error": None
                    }
                else:
                    err_msg = f"WhatsApp API error HTTP {resp.status_code}: {resp.text}"
                    logger.error(err_msg)
                    return {
                        "success": False,
                        "provider": "whatsapp",
                        "provider_message_id": None,
                        "error": err_msg
                    }
        except Exception as e:
            logger.error(f"WhatsApp request failed: {e}")
            return {
                "success": False,
                "provider": "whatsapp",
                "provider_message_id": None,
                "error": str(e)
            }

    async def send_document(self, recipient: str, document_path: str, caption: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        target_phone = self._resolve_recipient(recipient)
        if not target_phone and not self.mock_mode:
            return {
                "success": False,
                "provider": "whatsapp",
                "provider_message_id": None,
                "error": "Missing recipient phone number"
            }

        if self._is_mock():
            logger.info(f"[MOCK WHATSAPP] Sending document '{document_path}' to {target_phone or 'mock_phone'}")
            return {
                "success": True,
                "provider": "whatsapp",
                "provider_message_id": f"mock_wa_doc_{uuid.uuid4().hex[:8]}",
                "error": None
            }

        # For real WhatsApp Cloud API, document parameter uses link or media id
        url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        # If document_path is a URL, use link; if local file, fallback/simulate link or handle missing URL
        doc_payload = {"caption": caption or "Document Attachment"}
        if document_path.startswith("http://") or document_path.startswith("https://"):
            doc_payload["link"] = document_path
        else:
            doc_payload["link"] = f"{settings.PUBLIC_BASE_URL}/files/{os.path.basename(document_path)}"

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": target_phone,
            "type": "document",
            "document": doc_payload
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code in [200, 201]:
                    res_json = resp.json()
                    msg_id = res_json.get("messages", [{}])[0].get("id", "")
                    return {
                        "success": True,
                        "provider": "whatsapp",
                        "provider_message_id": msg_id,
                        "error": None
                    }
                else:
                    err_msg = f"WhatsApp document send error HTTP {resp.status_code}: {resp.text}"
                    logger.error(err_msg)
                    return {
                        "success": False,
                        "provider": "whatsapp",
                        "provider_message_id": None,
                        "error": err_msg
                    }
        except Exception as e:
            logger.error(f"WhatsApp document request failed: {e}")
            return {
                "success": False,
                "provider": "whatsapp",
                "provider_message_id": None,
                "error": str(e)
            }

    async def send_image(self, recipient: str, image_path: str, caption: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        target_phone = self._resolve_recipient(recipient)
        if not target_phone and not self.mock_mode:
            return {
                "success": False,
                "provider": "whatsapp",
                "provider_message_id": None,
                "error": "Missing recipient phone number"
            }

        if self._is_mock():
            logger.info(f"[MOCK WHATSAPP] Sending image '{image_path}' to {target_phone or 'mock_phone'}")
            return {
                "success": True,
                "provider": "whatsapp",
                "provider_message_id": f"mock_wa_img_{uuid.uuid4().hex[:8]}",
                "error": None
            }

        url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        img_payload = {"caption": caption or "Image Attachment"}
        if image_path.startswith("http://") or image_path.startswith("https://"):
            img_payload["link"] = image_path
        else:
            img_payload["link"] = f"{settings.PUBLIC_BASE_URL}/files/{os.path.basename(image_path)}"

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": target_phone,
            "type": "image",
            "image": img_payload
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code in [200, 201]:
                    res_json = resp.json()
                    msg_id = res_json.get("messages", [{}])[0].get("id", "")
                    return {
                        "success": True,
                        "provider": "whatsapp",
                        "provider_message_id": msg_id,
                        "error": None
                    }
                else:
                    err_msg = f"WhatsApp image send error HTTP {resp.status_code}: {resp.text}"
                    logger.error(err_msg)
                    return {
                        "success": False,
                        "provider": "whatsapp",
                        "provider_message_id": None,
                        "error": err_msg
                    }
        except Exception as e:
            logger.error(f"WhatsApp image request failed: {e}")
            return {
                "success": False,
                "provider": "whatsapp",
                "provider_message_id": None,
                "error": str(e)
            }
