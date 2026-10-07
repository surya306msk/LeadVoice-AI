import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.schemas import HealthResponse
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger("leadvoice.api.health")

@router.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="healthy")

@router.get("/health/ready")
def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness check endpoint that verifies database connection and application state
    without executing third-party paid API requests.
    """
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.error(f"Readiness check failed - DB error: {e}")
        raise HTTPException(status_code=503, detail="Database connection unavailable")

    return {
        "status": "ready",
        "database": db_status,
        "mock_mode": settings.MOCK_MODE,
        "voice_provider": settings.VOICE_PROVIDER,
        "messaging_provider": settings.MESSAGING_PROVIDER
    }
