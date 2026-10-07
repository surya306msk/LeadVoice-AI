import logging
from typing import Optional, Union
from app.models.schemas import LeadAnalysis
from app.models.database_models import Lead
from app.services.message_builder_service import MessageBuilderService

logger = logging.getLogger("leadvoice.services.followup")

class FollowupService:
    """
    Service to generate tailored follow-up messages based on lead classification and facts.
    """

    def __init__(self):
        self.builder = MessageBuilderService()

    def generate_followup(
        self,
        analysis: Union[LeadAnalysis, dict],
        lead: Optional[Union[Lead, dict]] = None,
        callback_time_str: Optional[str] = None
    ) -> str:
        if isinstance(analysis, LeadAnalysis):
            status = analysis.lead_status
        elif isinstance(analysis, dict):
            status = analysis.get("lead_status", "COLD")
        else:
            status = "COLD"

        if status == "HOT":
            return self.builder.build_hot_lead_alert(analysis, lead)
        elif status == "WARM":
            return self.builder.build_warm_followup(analysis, lead, callback_time_str)
        else: # COLD
            return self.builder.build_cold_followup(analysis, lead)
