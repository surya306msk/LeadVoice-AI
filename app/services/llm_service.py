import json
import logging
import re
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
        """Analyze conversation transcript via mock (MOCK_MODE) or Groq API."""
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
            "Content-Type": "application/json",
        }
        payload = {
            "model": "llama3-8b-8192",
            "messages": [
                {"role": "system", "content": LEAD_ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 1000,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(self.groq_api_url, headers=headers, json=payload)

            if response.status_code != 200:
                logger.error(f"Groq API error. Status: {response.status_code}, Body: {response.text}")
                raise httpx.HTTPStatusError(
                    "Groq API returned non-200 status",
                    request=response.request,
                    response=response,
                )

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed_content = json.loads(content)
            return LeadAnalysis(**parsed_content)

        except json.JSONDecodeError as jde:
            logger.error(f"Failed to parse JSON from Groq response: {jde}")
            raise ValueError("Invalid JSON response from LLM") from jde
        except Exception as e:
            logger.error(f"Error calling Groq: {e}")
            raise

    def _mock_analysis(
        self,
        conversation: str,
        existing_lead_data: Optional[Dict[str, Any]] = None,
    ) -> LeadAnalysis:
        """
        Regex-based mock analyzer for MOCK_MODE and tests.
        Extracts structured lead data from natural-language conversations
        in English, Hindi/Hinglish, and Telugu/Teluglish without hallucinating
        missing fields.
        """

        # Default output template
        analysis_dict: Dict[str, Any] = {
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
            "conversation_summary": conversation[:200],
        }

        # Carry forward fields from previous turns (progressive extraction)
        if existing_lead_data:
            for key, val in existing_lead_data.items():
                if val is not None and key in analysis_dict:
                    analysis_dict[key] = val

        lc = conversation.lower()

        # --- Language detection ---
        telugu_markers = [
            "namaskaram", "meeru", "nenu", "cheppandi", "adigite",
            "kavali", "chestunam", "rupayalu", "mee", "meeku",
            "chestham", "vunte", "unnai", "unnayi", "vereega",
        ]
        hindi_markers = [
            "namaste", "chahiye", "mujhe", "karna", "rupaye",
            "lakh", "mahine", "hafte", "abhi", "bahut", "haan",
            "aapka", "nahi", "shuru", "sirf", "agle",
        ]
        telugu_hit = sum(1 for m in telugu_markers if m in lc)
        hindi_hit  = sum(1 for m in hindi_markers  if m in lc)
        if telugu_hit >= 2:
            analysis_dict["language"] = "Telugu"
        elif hindi_hit >= 2:
            analysis_dict["language"] = "Hindi"

        # --- Business type ---
        biz_patterns = [
            (r"\be[\-\s]?commerce\b",                                       "e-commerce"),
            (r"\bonline\s+store\b|\bonline\s+shop\b",                        "Online Store"),
            (r"\bshopping\s+(website|site|portal)\b",                        "Online Store"),
            (r"\b(handmade\s+)?jewell?ery\b",                               "Handmade Jewellery"),
            (r"\bimitation\s+jewell?ery\b",                                 "Imitation Jewellery"),
            (r"\b(organic\s+)?food(s)?\b|\bgrocery\b|\bgroceries\b",        "Food & Groceries"),
            (r"\brestaurant\b|\bcafe\b|\bbakery\b",                         "Food & Beverage"),
            (r"\b(clothing|clothes|garments?|fashion|sarees?|kurtis?)\b",   "Clothing & Fashion"),
            (r"\belectronics?\b|\bgadgets?\b",                              "Electronics"),
            (r"\bhandicraft\b|\bhandmade\b|\bhandcraft\b",                  "Handicrafts"),
            (r"\bpharmacy\b|\bmedical\s+store\b|\bdrug\s+store\b",         "Pharmacy"),
            (r"\bfurniture\b|\bhome\s+decor\b|\binterior\b",               "Furniture & Home Decor"),
            (r"\bbooks?\b|\bstationery\b",                                  "Books & Stationery"),
            (r"\bbusiness\s+website\b|\bcompany\s+website\b",              "Business Website"),
        ]
        if not analysis_dict["business_type"]:
            for pattern, biz_type in biz_patterns:
                if re.search(pattern, lc):
                    analysis_dict["business_type"] = biz_type
                    break

        # --- Product count ---
        # Supports English ("500 products"), Hindi ("chahiye"), Telugu ("kavali")
        if analysis_dict["product_count"] is None:
            product_count_patterns = [
                r"(?:around|about|approximately|roughly|nearly|close\s+to|over|"
                r"more\s+than|upto|up\s+to)?\s*(\d[\d,]*)\s*"
                r"(?:products?|items?|skus?|listings?)",
                r"(?:have|has|having|will\s+be|are|about)\s+(\d[\d,]*)\s*"
                r"(?:products?|items?|skus?)",
                r"(\d[\d,]*)\s*(?:se\s+zyada\s+)?(?:products?|items?)"
                r"\s*(?:chahiye|hai|hain)?",
                r"(\d[\d,]*)\s*(?:products?|items?)\s*(?:kavali|unnai|unnayi)?",
            ]
            for pat in product_count_patterns:
                m = re.search(pat, lc)
                if m:
                    raw = m.group(1).replace(",", "")
                    analysis_dict["product_count"] = int(raw)
                    if not analysis_dict["products"]:
                        analysis_dict["products"] = "Products"
                    break

        # --- Budget ---
        # Supports: ₹1,00,000 / Rs. / INR prefix; lakh (word & numeric);
        # "k" suffix; raw rupee amounts; English word-based thousands.
        if analysis_dict["budget"] is None:
            budget_inr = None

            sym_m = re.search(
                r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)\s*(lakh|lac|l\b)?", lc
            )
            if sym_m:
                raw = sym_m.group(1).replace(",", "")
                val = float(raw)
                if sym_m.group(2):
                    val *= 100_000
                budget_inr = int(val)

            if budget_inr is None:
                lakh_m = re.search(r"([\d.]+)\s*(?:lakh|lac|lakhs|lacs)\b", lc)
                if lakh_m:
                    try:
                        budget_inr = int(float(lakh_m.group(1)) * 100_000)
                    except ValueError:
                        pass

            if budget_inr is None:
                word_lakh = {
                    r"\b(?:one|ek|oka|1)\s+lakh\b": 100_000,
                    r"\b(?:two|do|2)\s+lakhs?\b":    200_000,
                    r"\b(?:three|teen|3)\s+lakhs?\b": 300_000,
                    r"\bhalf\s+a\s+lakh\b":           50_000,
                }
                for pat, val in word_lakh.items():
                    if re.search(pat, lc):
                        budget_inr = val
                        break

            if budget_inr is None:
                k_m = re.search(r"\b(\d+(?:\.\d+)?)\s*k\b", lc)
                if k_m:
                    budget_inr = int(float(k_m.group(1)) * 1_000)

            if budget_inr is None:
                raw_pats = [
                    r"(\d[\d,]+)\s*(?:rupees?|rupaiye?|rupayalu|inr|/-)",
                    r"budget\s+(?:is\s+|of\s+|around\s+|about\s+)?([\d,]+)",
                ]
                for pat in raw_pats:
                    m = re.search(pat, lc)
                    if m:
                        raw = m.group(1).replace(",", "")
                        val = int(raw)
                        if val >= 1000:
                            budget_inr = val
                            break

            if budget_inr is None:
                word_thousands = {
                    r"\beighty[\s\-]?thousand\b":     80_000,
                    r"\bfifty[\s\-]?thousand\b":      50_000,
                    r"\bsixty[\s\-]?thousand\b":      60_000,
                    r"\bseventy[\s\-]?thousand\b":    70_000,
                    r"\bninety[\s\-]?thousand\b":     90_000,
                    r"\bone\s+hundred\s+thousand\b": 100_000,
                }
                for pat, val in word_thousands.items():
                    if re.search(pat, lc):
                        budget_inr = val
                        break

            if budget_inr is not None:
                analysis_dict["budget"] = f"{budget_inr} INR"

        # --- Timeline ---
        # Supports days/weeks/months (numeric & word-based), ASAP,
        # Hindi (hafte/mahine) and Telugu (nela).
        if analysis_dict["timeline"] is None:
            timeline_str = None

            m = re.search(r"(\d+)\s*(?:days?|din)\b", lc)
            if m:
                timeline_str = f"{m.group(1)} days"

            if not timeline_str:
                m = re.search(r"(\d+)\s*(?:weeks?|hafte?|hafton?)\b", lc)
                if m:
                    n = int(m.group(1))
                    timeline_str = f"{n} week" if n == 1 else f"{n} weeks"

            if not timeline_str:
                m = re.search(r"(\d+)\s*(?:months?|mahine?|mahino?|nela)\b", lc)
                if m:
                    n = int(m.group(1))
                    timeline_str = f"{n} month" if n == 1 else f"{n} months"

            if not timeline_str and re.search(
                r"\b(?:one|ek|oka|1)\s+(?:month|mahina|mahine|nela)\b", lc
            ):
                timeline_str = "1 month"

            if not timeline_str and re.search(r"\bwithin\s+(?:a|one|1)\s+month\b", lc):
                timeline_str = "1 month"

            if not timeline_str and re.search(
                r"\bnext\s+month\b|\bagle\s+mahine\b|\bcoming\s+month\b", lc
            ):
                timeline_str = "1 month"

            if not timeline_str and re.search(
                r"\bby\s+(?:end\s+of\s+(?:this\s+)?month|month\s+end)\b", lc
            ):
                timeline_str = "1 month"

            if not timeline_str and re.search(
                r"\basap\b|\bimmediately\b|\burgent(ly)?\b|\bjaldi\b|\bturant\b|\bvereega\b", lc
            ):
                timeline_str = "ASAP"

            if timeline_str:
                analysis_dict["timeline"] = timeline_str

        # --- Decision maker ---
        dm_patterns = [
            (r"\bfounder\b",                                    "Founder"),
            (r"\b(?:business\s+)?owner\b",                      "Owner"),
            (r"\bceo\b|\bchief\s+executive\b",                  "CEO"),
            (r"\bdirector\b",                                   "Director"),
            (r"\bpartner\b",                                    "Partner"),
            (r"\bbrother\b|\bbhai\b|\banna\b",                  "Brother"),
            (r"\bwife\b|\bhusband\b|\bspouse\b",                "Spouse"),
            (r"\bmanager\b",                                    "Manager"),
            (r"\bi\s+am\s+(?:the\s+)?decision\s+maker\b",       "Customer"),
            (r"\bi\s+(?:decide|make\s+(?:the\s+)?decision)\b", "Customer"),
        ]
        if analysis_dict.get("decision_maker") in (None, "Customer"):
            for pattern, dm_label in dm_patterns:
                if re.search(pattern, lc):
                    analysis_dict["decision_maker"] = dm_label
                    break

        # --- Features ---
        feature_map = {
            r"\bonline\s+pay(?:ment)?s?\b|\bpayment\s+gateway\b|\brazorpay\b|\bpaytm\b|\bupi\b":
                "Online Payments",
            r"\bproduct\s+catalo(?:g|gue)\b|\bcatalog\b":
                "Product Catalogue",
            r"\border\s+track(?:ing)?\b":
                "Order Tracking",
            r"\badmin\s+(?:panel|dashboard)\b|\bdashboard\b":
                "Admin Dashboard",
            r"\bwhatsapp\s+(?:integration|chat|support)\b":
                "WhatsApp Integration",
            r"\b(?:search|filter)\b":
                "Search & Filter",
            r"\bwishlist\b|\bsave\s+for\s+later\b":
                "Wishlist",
            r"\b(?:shopping\s+)?cart\b":
                "Shopping Cart",
            r"\bmultipl?e?\s+languages?\b|\bmultilingual\b":
                "Multilingual Support",
            r"\bmobile\s+(?:app|friendly|responsive)\b|\bresponsive\b":
                "Mobile Responsive",
            r"\bseo\b|\bsearch\s+engine\s+optim":
                "SEO",
            r"\bcoupon\b|\bdiscount\b|\bpromo(?:tion)?\b":
                "Coupons & Discounts",
            r"\binventory\b|\bstock\s+management\b":
                "Inventory Management",
            r"\bdelivery\s+track(?:ing)?\b|\bshipping\b|\blogistics\b":
                "Delivery Tracking",
            r"\breview\b|\brating\b":
                "Reviews & Ratings",
        }
        existing_features: set = set(analysis_dict.get("features") or [])
        for pat, feat in feature_map.items():
            if re.search(pat, lc):
                existing_features.add(feat)
        analysis_dict["features"] = sorted(existing_features)

        # --- Barrier ---
        # Pattern allows arbitrary words between "my" and the person-noun
        # (e.g. "discuss … with my business partner").
        barrier_patterns = [
            (
                r"\bdiscuss\b.{0,40}\bmy\b.{0,30}\b(?:partner|husband|wife|brother|bhai|anna)\b"
                r"|\bpartner\s+approv(?:al|e)\b",
                "Needs partner/family approval",
            ),
            (
                r"\bbudget\s+(?:not\s+)?(?:finalized?|confirmed?|decided?|approved?)\b"
                r"|\bnot\s+sure\s+(?:about\s+)?(?:the\s+)?budget\b",
                "Budget not finalized",
            ),
            (
                r"\bwaiting\s+for\s+(?:funds?|money|capital|investment)\b",
                "Waiting for funds",
            ),
            (
                r"\bnot\s+(?:ready|sure)\s+(?:yet|now)\b",
                "Not ready yet",
            ),
            (
                r"\bthink(?:ing)?\s+(?:about|over)\b|\bconsider(?:ing)?\b",
                "Still considering",
            ),
        ]
        if not analysis_dict.get("barrier"):
            for pat, barrier_label in barrier_patterns:
                if re.search(pat, lc, re.DOTALL):
                    analysis_dict["barrier"] = barrier_label
                    break

        # --- Callback detection ---
        callback_expressions = [
            (r"\btomorrow\s+morning\b",                          "tomorrow morning"),
            (r"\btomorrow\s+afternoon\b",                        "tomorrow afternoon"),
            (r"\btomorrow\s+evening\b",                          "tomorrow evening"),
            (r"\btomorrow\b",                                    "tomorrow"),
            (r"\bthis\s+(?:evening|afternoon|morning)\b",        "this evening"),
            (r"\blater\s+today\b|\bafter\s+(?:lunch|dinner)\b",  "later today"),
            (r"\bnext\s+week\b",                                 "next week"),
            (
                r"\b(?:call|ring|contact|phone)\s+me\s+(?:back|later|tomorrow|again)\b",
                "callback requested",
            ),
        ]
        if not analysis_dict.get("callback_expression"):
            for pat, expr in callback_expressions:
                if re.search(pat, lc):
                    analysis_dict["callback_requested"] = True
                    analysis_dict["callback_expression"] = expr
                    break
        elif analysis_dict.get("callback_expression"):
            analysis_dict["callback_requested"] = True

        # --- Lead classification (HOT / WARM / COLD) ---
        hot_signal_patterns = [
            r"\bready\s+to\s+(?:proceed|start|begin|go\s+ahead|pay|sign)\b",
            r"\blet'?s?\s+(?:start|begin|proceed|go\s+ahead)\b",
            r"\bwant\s+to\s+(?:start|proceed|begin|go\s+ahead)\b",
            r"\b(?:confirm|finaliz(?:e|ing)|book(?:ing)?|order(?:ing)?)\b",
            r"\bhow\s+(?:much|soon)\s+(?:can\s+you|do\s+you|will\s+you)\b",
            r"\bwhen\s+can\s+(?:you\s+)?start\b",
            r"\bproceed\s+soon\b|\bstart\s+(?:soon|asap|immediately|the\s+work|the\s+project)\b",
            r"\bwant\s+(?:it|the\s+website|this)\s+(?:completed?|done|ready|launched?|built)\b",
            r"\bdecision\s+maker\b",
            r"\bshuru\s+(?:karo|karna|kar)\b|\bstart\s+karo\b",       # Hindi
            r"\bprarambi(?:nchu|ndam)\b|\bcheyandi\b",                 # Telugu
        ]
        warm_signal_patterns = [
            r"\bdiscuss\b",
            r"\bthink(?:ing)?\s+(?:about|over)\b",
            r"\bneed\s+to\s+(?:check|confirm|ask|discuss|talk)\b",
            r"\bnot\s+(?:sure|confirmed?|finalized?)\b",
            r"\bmaybe\b|\bperhaps\b|\bpossibly\b",
            r"\bwill\s+(?:let|get\s+back|call\s+you\s+back)\b",
            r"\bcall\s+(?:me\s+)?back\b",
            r"\bapproval\b",
        ]
        cold_signal_patterns = [
            r"\bjust\s+(?:checking|browsing|exploring|looking)\b",
            r"\bno\s+(?:immediate|urgent|current)\s+(?:plan|requirement|need|budget)\b",
            r"\bnot\s+(?:now|yet|interested|ready)\b",
            r"\bjust\s+curious\b",
            r"\bjust\s+(?:want|wanted)\s+to\s+know\b",
            r"\bno\s+immediate\s+plans?\b|\bdon'?t\s+have\s+any\s+immediate\s+plans?\b",
            r"\bsirf\s+(?:dekh|jaan)\b",       # Hindi
            r"\bchustunnanu\s+matrame\b",       # Telugu
        ]

        has_budget   = bool(analysis_dict["budget"])
        has_timeline = bool(analysis_dict["timeline"])

        hot_hit  = sum(1 for p in hot_signal_patterns  if re.search(p, lc))
        warm_hit = sum(1 for p in warm_signal_patterns if re.search(p, lc))
        cold_hit = sum(1 for p in cold_signal_patterns if re.search(p, lc))

        # Active barrier prevents HOT even when budget+timeline are present
        has_active_barrier = bool(analysis_dict["barrier"]) or analysis_dict["callback_requested"]

        is_hot = (
            (hot_hit >= 1 and (has_budget or has_timeline))
            or (has_budget and has_timeline and not has_active_barrier)
        )
        is_warm = not is_hot and (
            has_active_barrier
            or (warm_hit >= 1 and cold_hit == 0)
        )

        current_status = analysis_dict.get("lead_status", "COLD")

        if is_hot:
            analysis_dict["lead_status"] = "HOT"
            analysis_dict["recommended_action"] = "SEND_WHATSAPP_NOW"
            parts = []
            if has_budget:   parts.append(f"budget ({analysis_dict['budget']})")
            if has_timeline: parts.append(f"timeline ({analysis_dict['timeline']})")
            if hot_hit:      parts.append("strong purchase intent")
            analysis_dict["reason"] = (
                "Customer shows HOT lead signals: " + ", ".join(parts) + "."
                if parts else "Customer shows strong purchase intent."
            )

        elif is_warm:
            analysis_dict["lead_status"] = "WARM"
            analysis_dict["recommended_action"] = (
                "SCHEDULE_CALLBACK" if analysis_dict["callback_requested"] else "SEND_FOLLOWUP"
            )
            barrier_txt = (
                analysis_dict.get("barrier") or "has a barrier or needs to confirm details"
            )
            cb_note = "Callback was requested." if analysis_dict["callback_requested"] else ""
            analysis_dict["reason"] = f"Customer shows interest but {barrier_txt}. {cb_note}".strip()

        elif cold_hit > 0:
            analysis_dict["lead_status"] = "COLD"
            analysis_dict["recommended_action"] = "SEND_FOLLOWUP"
            analysis_dict["reason"] = (
                "Customer is only exploring and does not have an immediate requirement."
            )

        elif current_status == "HOT":
            # Preserve HOT from prior turns when no downgrade signal exists
            analysis_dict["lead_status"] = "HOT"
            analysis_dict["recommended_action"] = "SEND_WHATSAPP_NOW"

        return LeadAnalysis(**analysis_dict)
