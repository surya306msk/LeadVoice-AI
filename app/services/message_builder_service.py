import logging
from typing import Optional, Dict, Any, Union
from app.models.schemas import LeadAnalysis
from app.models.database_models import Lead

logger = logging.getLogger("leadvoice.services.message_builder")

class MessageBuilderService:
    """
    Builds structured, personalized messages from verified Lead / LeadAnalysis data.
    Strictly avoids inventing or guessing missing details.
    """

    @staticmethod
    def _extract_field(source: Any, field_name: str, fallback: Any = None) -> Any:
        if source is None:
            return fallback
        if isinstance(source, dict):
            return source.get(field_name, fallback)
        if hasattr(source, field_name):
            val = getattr(source, field_name)
            return val if val is not None else fallback
        return fallback

    @classmethod
    def build_hot_lead_alert(
        cls,
        analysis: Union[LeadAnalysis, dict],
        lead: Optional[Union[Lead, dict]] = None
    ) -> str:
        # Extract fields from analysis or lead
        name = cls._extract_field(lead, "customer_name") or cls._extract_field(analysis, "customer_name")
        phone = cls._extract_field(lead, "phone_number") or cls._extract_field(analysis, "phone_number")
        biz_type = cls._extract_field(analysis, "business_type") or cls._extract_field(lead, "business_type")
        products = cls._extract_field(analysis, "products") or cls._extract_field(lead, "products_sold")
        p_count = cls._extract_field(analysis, "product_count") or cls._extract_field(lead, "approximate_product_count")
        budget = cls._extract_field(analysis, "budget") or cls._extract_field(lead, "budget")
        timeline = cls._extract_field(analysis, "timeline") or cls._extract_field(lead, "timeline")
        features = cls._extract_field(analysis, "features") or cls._extract_field(lead, "required_features")
        decision_maker = cls._extract_field(analysis, "decision_maker") or cls._extract_field(lead, "decision_maker")
        barrier = cls._extract_field(analysis, "barrier") or cls._extract_field(lead, "objections_or_barriers")
        reason = cls._extract_field(analysis, "reason") or cls._extract_field(lead, "reason_for_classification")

        lines = ["🚨 HOT LEAD ALERT 🚨\n"]

        details = []
        if name:
            details.append(f"• Name: {name}")
        if phone:
            details.append(f"• Phone: {phone}")
        if biz_type:
            details.append(f"• Business Type: {biz_type}")
        if products:
            prod_str = f"{products}"
            if p_count:
                prod_str += f" (Count: {p_count})"
            details.append(f"• Products: {prod_str}")
        elif p_count:
            details.append(f"• Product Count: {p_count}")
        if budget:
            details.append(f"• Budget: {budget}")
        if timeline:
            details.append(f"• Timeline: {timeline}")
        if features:
            if isinstance(features, list):
                feat_str = ", ".join(features)
            else:
                feat_str = str(features)
            if feat_str.strip():
                details.append(f"• Features: {feat_str}")
        if decision_maker:
            details.append(f"• Decision Maker: {decision_maker}")
        if barrier:
            details.append(f"• Objection/Barrier: {barrier}")

        if details:
            lines.append("Lead Details:")
            lines.extend(details)
            lines.append("")

        lines.append("Classification: HOT")
        if reason:
            lines.append(f"Reason: {reason}")

        return "\n".join(lines)

    @classmethod
    def build_warm_followup(
        cls,
        analysis: Union[LeadAnalysis, dict],
        lead: Optional[Union[Lead, dict]] = None,
        callback_time_str: Optional[str] = None
    ) -> str:
        name = cls._extract_field(lead, "customer_name") or cls._extract_field(analysis, "customer_name")
        barrier = cls._extract_field(analysis, "barrier") or cls._extract_field(lead, "objections_or_barriers")
        cb_expr = cls._extract_field(analysis, "callback_expression") or cls._extract_field(lead, "callback_request")

        salutation = f"Hello {name}," if name else "Hello,"
        lines = [salutation, "\nThank you for reaching out to us!"]

        if barrier:
            lines.append(f"Regarding your query/concern about '{barrier}', our team is preparing customized options for you.")

        if callback_time_str:
            lines.append(f"We have scheduled a callback for you on {callback_time_str}.")
        elif cb_expr:
            lines.append(f"We noted your callback request: '{cb_expr}' and will contact you shortly.")

        lines.append("\nPlease let us know if you have any additional details to share in the meantime.")
        lines.append("Best regards,\nLeadVoice AI Team")

        return "\n".join(lines)

    @classmethod
    def build_cold_followup(
        cls,
        analysis: Union[LeadAnalysis, dict],
        lead: Optional[Union[Lead, dict]] = None
    ) -> str:
        name = cls._extract_field(lead, "customer_name") or cls._extract_field(analysis, "customer_name")
        summary = cls._extract_field(analysis, "conversation_summary") or cls._extract_field(lead, "conversation_summary")

        salutation = f"Hello {name}," if name else "Hello,"
        lines = [salutation, "\nThank you for your interest in our services."]

        if summary:
            lines.append(f"\nSummary of our conversation: {summary}")

        lines.append("\nFeel free to contact us whenever you are ready to explore further or have any questions.")
        lines.append("Best regards,\nLeadVoice AI Team")

        return "\n".join(lines)
