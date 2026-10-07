from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class BaseVoiceService(ABC):
    """
    Abstract Base Class for Voice Providers (Mock, Retell).
    Isolates provider-specific telephony implementation details.
    """

    @abstractmethod
    async def start_call(self, phone_number: str, customer_name: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Initiate a call session.
        """
        pass

    @abstractmethod
    async def process_user_message(self, call_id: str, message: str, **kwargs) -> Dict[str, Any]:
        """
        Process user speech/transcript turn and generate agent response.
        """
        pass

    @abstractmethod
    async def generate_agent_response(self, call_id: str, message: str, **kwargs) -> Dict[str, Any]:
        """
        Generate agent response text.
        """
        pass

    @abstractmethod
    async def end_call(self, call_id: str, **kwargs) -> Dict[str, Any]:
        """
        End call session and perform post-call tasks.
        """
        pass
