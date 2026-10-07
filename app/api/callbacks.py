from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from app.database.database import get_db
from app.models.database_models import ScheduledCallback, Lead
from app.models.schemas import (
    CallbackParseRequest,
    CallbackParseResponse,
    CallbackScheduleRequest,
    CallbackResponse
)
from app.services.callback_parser_service import CallbackParserService
from app.services.scheduler_service import SchedulerService

router = APIRouter(prefix="/api/callbacks", tags=["callbacks"])

# Dependency Providers
def get_parser_service():
    return CallbackParserService()

def get_scheduler_service():
    return SchedulerService()

@router.post("/parse", response_model=CallbackParseResponse)
async def parse_callback_expression(
    payload: CallbackParseRequest,
    parser: CallbackParserService = Depends(get_parser_service)
):
    if not payload.callback_expression or not payload.callback_expression.strip():
        raise HTTPException(status_code=400, detail="Callback expression cannot be empty.")
    
    response = await parser.parse_callback(
        callback_expression=payload.callback_expression,
        reference_time=payload.reference_time
    )
    return response

@router.post("/schedule", response_model=CallbackResponse)
async def schedule_callback_endpoint(
    payload: CallbackScheduleRequest,
    db: Session = Depends(get_db),
    parser: CallbackParserService = Depends(get_parser_service),
    scheduler_service: SchedulerService = Depends(get_scheduler_service)
):
    # Validate lead exists
    lead = db.query(Lead).filter(Lead.id == payload.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead with ID {payload.lead_id} not found.")

    if not payload.callback_expression or not payload.callback_expression.strip():
        raise HTTPException(status_code=400, detail="Callback expression cannot be empty.")

    # Parse the expression
    parse_result = await parser.parse_callback(payload.callback_expression)
    
    # Save database model
    db_callback = ScheduledCallback(
        lead_id=payload.lead_id,
        call_id=payload.call_id,
        original_expression=payload.callback_expression,
        scheduled_at=parse_result.scheduled_at,
        timezone=parse_result.timezone,
        status="SCHEDULED",
        assumption=parse_result.assumption
    )
    db.add(db_callback)
    db.commit()
    db.refresh(db_callback)

    # Schedule with APScheduler
    if parse_result.scheduled_at:
        scheduler_service.schedule_callback(db, db_callback.id)
    else:
        # If we couldn't parse a target time, update status to FAILED or leave as SCHEDULED but not loaded
        db_callback.status = "FAILED"
        db.commit()
        raise HTTPException(
            status_code=422,
            detail="A specific callback date and time could not be determined from the expression."
        )

    # Return CallbackResponse
    return CallbackResponse(
        callback_id=db_callback.id,
        lead_id=db_callback.lead_id,
        call_id=db_callback.call_id,
        original_expression=db_callback.original_expression,
        scheduled_at=db_callback.scheduled_at,
        timezone=db_callback.timezone,
        status=db_callback.status,
        assumption=db_callback.assumption,
        created_at=db_callback.created_at
    )

@router.get("", response_model=List[CallbackResponse])
def get_all_callbacks(db: Session = Depends(get_db)):
    callbacks = db.query(ScheduledCallback).all()
    # Map model attributes to CallbackResponse manually to resolve any property names
    return [
        CallbackResponse(
            callback_id=cb.id,
            lead_id=cb.lead_id,
            call_id=cb.call_id,
            original_expression=cb.original_expression,
            scheduled_at=cb.scheduled_at,
            timezone=cb.timezone,
            status=cb.status,
            assumption=cb.assumption,
            created_at=cb.created_at
        ) for cb in callbacks
    ]

@router.get("/{callback_id}", response_model=CallbackResponse)
def get_callback_by_id(callback_id: int, db: Session = Depends(get_db)):
    cb = db.query(ScheduledCallback).filter(ScheduledCallback.id == callback_id).first()
    if not cb:
        raise HTTPException(status_code=404, detail=f"Callback with ID {callback_id} not found.")
    
    return CallbackResponse(
        callback_id=cb.id,
        lead_id=cb.lead_id,
        call_id=cb.call_id,
        original_expression=cb.original_expression,
        scheduled_at=cb.scheduled_at,
        timezone=cb.timezone,
        status=cb.status,
        assumption=cb.assumption,
        created_at=cb.created_at
    )

@router.delete("/{callback_id}", response_model=CallbackResponse)
def cancel_callback_endpoint(
    callback_id: int,
    db: Session = Depends(get_db),
    scheduler_service: SchedulerService = Depends(get_scheduler_service)
):
    cb = db.query(ScheduledCallback).filter(ScheduledCallback.id == callback_id).first()
    if not cb:
        raise HTTPException(status_code=404, detail=f"Callback with ID {callback_id} not found.")
    
    scheduler_service.cancel_callback(db, callback_id)
    return CallbackResponse(
        callback_id=cb.id,
        lead_id=cb.lead_id,
        call_id=cb.call_id,
        original_expression=cb.original_expression,
        scheduled_at=cb.scheduled_at,
        timezone=cb.timezone,
        status=cb.status,
        assumption=cb.assumption,
        created_at=cb.created_at
    )
