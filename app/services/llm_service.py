import json
import logging
import httpx
from typing import Optional, Dict, Any
from app.core.config import settings
from app.models.schemas import LeadAnalysis
from app.prompts.lead_analysis_prompt import LEAD_ANALYSIS_SYSTEM_PROMPT

logger = logging.getLogger("leadvoice.llm")

class LLMService:
    def __init__(self):
        self.groq_api_url = "https://api.groq.com/openai/v1/chat/completions"

    async def analyze_conversation(
        self,
        conversation: str,
        existing_lead_data: Optional[Dict[str, Any]] = None
    ) -> LeadAnalysis:
        """
        Analyzes conversation transcript.
        If settings.MOCK_MODE is True, runs deterministic local mock analysis.
        Otherwise, communicates with Groq API.
        """
        if settings.MOCK_MODE:
            logger.info("MOCK_MODE is active. Using mock analyzer.")
            return self._mock_analysis(conversation, existing_lead_data)

        if not settings.GROQ_API_KEY or settings.GROQ_API_KEY.startswith("mock"):
            logger.warning("GROQ_API_KEY not configured. Falling back to mock analyzer.")
            return self._mock_analysis(conversation, existing_lead_data)

        return await self._call_groq(conversation, existing_lead_data)

    async def _call_groq(
        self,
        conversation: str,
        existing_lead_data: Optional[Dict[str, Any]] = None
    ) -> LeadAnalysis:
        logger.info("Querying Groq API for lead analysis...")
        
        user_content = f"Conversation History:\n{conversation}\n\n"
        if existing_lead_data:
            user_content += f"Existing Lead Data (JSON):\n{json.dumps(existing_lead_data)}\n\n"
        user_content += "Please output the analysis in JSON format as specified."

        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "llama3-8b-8192",
            "messages": [
                {"role": "system", "content": LEAD_ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 1000
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(self.groq_api_url, headers=headers, json=payload)
                
            if response.status_code != 200:
                logger.error(f"Groq API error. Status: {response.status_code}, Body: {response.text}")
                raise httpx.HTTPStatusError("Groq API returned non-200 status", request=response.request, response=response)

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed_content = json.loads(content)
            
            # Validate output using Pydantic
            return LeadAnalysis(**parsed_content)

        except json.JSONDecodeError as jde:
            logger.error(f"Failed to parse JSON from Groq response: {jde}")
            raise ValueError("Invalid JSON response from LLM") from jde
        except Exception as e:
            logger.error(f"Error calling Groq: {e}")
            # Fall back to mock on critical failure if needed, or raise
            raise

    def _mock_analysis(
        self,
        conversation: str,
        existing_lead_data: Optional[Dict[str, Any]] = None
    ) -> LeadAnalysis:
        """
        Deterministic mock analyzer for local development and unit tests.
        """
        # Base template
        analysis_dict = {
            "language": "English",
            "business_type": None,
            "products": None,
            "product_count": None,
            "budget": None,
            "timeline": None,
            "features": [],
            "decision_maker": "Customer",
            "barrier": None,
            "callback_requested": False,
            "callback_expression": None,
            "lead_status": "COLD",
            "confidence": 0.95,
            "reason": "Initial baseline classification.",
            "recommended_action": "SEND_FOLLOWUP",
            "conversation_summary": conversation[:100]
        }

        # Apply existing lead data if provided
        if existing_lead_data:
            for key, val in existing_lead_data.items():
                if val is not None and key in analysis_dict:
                    analysis_dict[key] = val

        lower_conv = conversation.lower()

        # Check for specific phrase templates or keywords
        if "exploring options" in lower_conv or "just checking" in lower_conv:
            analysis_dict["lead_status"] = "COLD"
            analysis_dict["recommended_action"] = "SEND_FOLLOWUP"
            analysis_dict["reason"] = "Customer is only exploring options and does not have an immediate requirement."

        if "300 products" in lower_conv or "300" in lower_conv:
            analysis_dict["products"] = "Products"
            analysis_dict["product_count"] = 300
            analysis_dict["reason"] = "Customer specified they have around 300 products."

        if "200 products" in lower_conv or "200" in lower_conv:
            analysis_dict["products"] = "Products"
            analysis_dict["product_count"] = 200

        if "handmade jewellery" in lower_conv or "jewellery" in lower_conv:
            analysis_dict["business_type"] = "Handmade Jewellery"
            analysis_dict["products"] = "Jewellery"

        if "150 products" in lower_conv or "150" in lower_conv:
            analysis_dict["product_count"] = 150

        if "80000" in lower_conv or "80000 rupees" in lower_conv:
            analysis_dict["budget"] = "80000 INR"

        if "one month" in lower_conv or "within a month" in lower_conv:
            analysis_dict["timeline"] = "1 month"

        # Check HOT triggers (budget and urgent timeline or specific HOT scenario request)
        if "one lakh" in lower_conv or "1 lakh" in lower_conv or "100000" in lower_conv:
            analysis_dict["budget"] = "100000 INR"
            
        if "next month" in lower_conv:
            analysis_dict["timeline"] = "1 month"

        # If we have budget and timeline and product count or a direct HOT mock request
        if ("one lakh" in lower_conv or "80000" in lower_conv) and ("one month" in lower_conv or "next month" in lower_conv or "within a month" in lower_conv):
            analysis_dict["lead_status"] = "HOT"
            analysis_dict["recommended_action"] = "SEND_WHATSAPP_NOW"
            analysis_dict["reason"] = "Customer has a defined budget, clear requirements, and urgent timeline."

        # Check WARM triggers
        if "discuss the budget" in lower_conv or "discuss it with my partner" in lower_conv or "partner" in lower_conv or "tomorrow morning" in lower_conv:
            analysis_dict["lead_status"] = "WARM"
            analysis_dict["recommended_action"] = "SCHEDULE_CALLBACK"
            analysis_dict["barrier"] = "Needs partner approval / discussion"
            analysis_dict["callback_requested"] = True
            analysis_dict["callback_expression"] = "tomorrow morning"
            analysis_dict["reason"] = "Customer shows interest but has a barrier (partner discussion) and requested a callback."

        # Return validated model
        return LeadAnalysis(**analysis_dict)
