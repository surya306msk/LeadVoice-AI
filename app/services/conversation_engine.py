import logging
import re
from typing import Optional, Dict, Any, List
from app.models.schemas import LeadAnalysis
from app.services.llm_service import LLMService
from app.core.config import settings

logger = logging.getLogger("leadvoice.services.conversation_engine")

class ConversationEngine:
    """Generates language-aware consultative agent responses based on extracted lead data."""

    def __init__(self):
        self.llm_service = LLMService()

    def detect_language(self, text: str, current_lang: Optional[str] = None) -> str:
        if not text:
            return current_lang or "English"
            
        lower = text.lower()
        
        # Telugu / Teluglish indicators
        telugu_keywords = ["naaku", "kavali", "undi", "vaddhu", "garu", "miru", "andi", "cheppandi", "enti", "ela", "website kavali"]
        if any(kw in lower for kw in telugu_keywords):
            return "Telugu"
            
        # Hindi / Hinglish indicators
        hindi_keywords = ["mujhe", "chahiye", "hai", "nahi", "batao", "aapka", "kya", "kaise", "karna", "lagbhag", "rupees"]
        if any(kw in lower for kw in hindi_keywords):
            return "Hindi"

        return current_lang or "English"

    def generate_response(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        analysis: LeadAnalysis,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Determines missing lead information and formulates a natural, consultative agent response.
        """
        detected_lang = self.detect_language(user_message, language or analysis.language)
        
        # Determine missing discovery items
        has_business = bool(analysis.business_type)
        has_products = bool(analysis.products) or bool(analysis.product_count)
        has_budget = bool(analysis.budget)
        has_timeline = bool(analysis.timeline)
        has_barrier = bool(analysis.barrier) or analysis.callback_requested

        agent_text = ""

        # Language specific conversational branches
        if detected_lang == "Telugu":
            if not has_business and not has_products:
                agent_text = "Chala manchidi! Meeru ae type business chestunnaru & enni products list cheddam anukuntunnaru?"
            elif has_business and not has_products:
                agent_text = "Got it! Roughly enni products list cheyalsi untundi?"
            elif has_products and not has_budget:
                agent_text = "Super. Ee project kosam mee budget range entha anukuntunnaru?"
            elif has_budget and not has_timeline:
                agent_text = "Artham ayyindi. Ee website ni eppatikalla launch cheyalanukuntunnaru?"
            else:
                if analysis.lead_status == "HOT":
                    agent_text = "Chala thanks info kosam! Mee requirements anni clear ga unnayi. Nenu ventane mana senior consultant ki mid-call alert pampinchanu, team mimmalni contact avvutaru."
                elif analysis.lead_status == "WARM":
                    agent_text = "Sure garu, mee query ni note cheskunanu. Nenu mee requested time ki callback schedule chestunnanu."
                else:
                    agent_text = "Mee details anni noted. Inka emaina doubts unte nannu adagavachu."

        elif detected_lang == "Hindi":
            if not has_business and not has_products:
                agent_text = "Bilkul! Aap kis tarah ka business karte hain aur kitne products online list karna chahenge?"
            elif has_business and not has_products:
                agent_text = "Samajh gaya. Approximately kitne products add karne ka plan hai?"
            elif has_products and not has_budget:
                agent_text = "Great. Kya aapne is project ke liye koi budget estimate socha hai?"
            elif has_budget and not has_timeline:
                agent_text = "Sahi hai. Aap is website ko kab tak launch karna chahte hain?"
            else:
                if analysis.lead_status == "HOT":
                    agent_text = "Bahut badiya! Aapki saari requirements note kar li hain. Humari team turant aapko priority contact karegi."
                elif analysis.lead_status == "WARM":
                    agent_text = "Ji bilkul, maine aapka callback note kar liya hai aur humari team fixed time par call karegi."
                else:
                    agent_text = "Aapki jankari ke liye dhanyawad. Agar aapke paas koi aur sawal ho toh zaroor bataiye."

        else: # English
            if not has_business and not has_products:
                agent_text = "Absolutely! What kind of business do you run, and what products do you plan to list?"
            elif has_business and not has_products:
                agent_text = "Got it. Approximately how many products would you like to list initially?"
            elif has_products and not has_budget:
                agent_text = "Great catalog size! Do you have a budget range in mind for this project?"
            elif has_budget and not has_timeline:
                agent_text = "Understood. And when would you like to launch the website?"
            else:
                if analysis.lead_status == "HOT":
                    agent_text = "Excellent! You have a clear vision and timeline. I am notifying our specialist team right away to get started."
                elif analysis.lead_status == "WARM":
                    agent_text = "Understood. I have logged your request and scheduled a callback as requested."
                else:
                    agent_text = "Thank you for sharing the details. Please feel free to reach out whenever you are ready to proceed."

        return {
            "agent_response": agent_text,
            "language": detected_lang
        }
