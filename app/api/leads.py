from fastapi import APIRouter, HTTPException, Depends
from app.models.schemas import AnalyzeLeadRequest, AnalyzeLeadResponse
from app.services.llm_service import LLMService
from app.core.config import settings
import logging

router = APIRouter(prefix="/api")
logger = logging.getLogger("leadvoice.api.leads")

# Dependency to get LLMService
def get_llm_service():
    return LLMService()

@router.post("/analyze-lead", response_model=AnalyzeLeadResponse)
async def analyze_lead(
    payload: AnalyzeLeadRequest,
    llm_service: LLMService = Depends(get_llm_service)
):
    if not payload.conversation or not payload.conversation.strip():
        raise HTTPException(status_code=400, detail="Conversation text cannot be empty.")
    
    try:
        analysis = await llm_service.analyze_conversation(
            conversation=payload.conversation,
            existing_lead_data=payload.existing_lead_data
        )
        
        source = "mock" if settings.MOCK_MODE or not settings.GROQ_API_KEY else "groq"
        
        return AnalyzeLeadResponse(
            analysis=analysis,
            source=source
        )
    except ValueError as ve:
        logger.error(f"Value error in lead analysis: {ve}")
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to analyze lead conversation: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while analyzing the conversation.")
