import logging
import pytz
from typing import Optional
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session
from app.core.config import settings
from app.database.database import SessionLocal
from app.models.database_models import ScheduledCallback

logger = logging.getLogger("leadvoice.scheduler")

# Instantiate a single global scheduler instance
scheduler = AsyncIOScheduler(timezone=pytz.timezone("Asia/Kolkata"))

# Mock execution job
async def execute_callback_job(callback_db_id: int):
    """
    Executed when the scheduled time arrives.
    Updates the database row and logs execution details.
    """
    db: Session = SessionLocal()
    try:
        callback = db.query(ScheduledCallback).filter(ScheduledCallback.id == callback_db_id).first()
        if not callback:
            logger.error(f"Callback job failed: Callback ID {callback_db_id} not found in database.")
            return

        if callback.status != "SCHEDULED":
            logger.warning(f"Callback ID {callback_db_id} was already processed or cancelled. Current status: {callback.status}")
            return

        # Execute mock logic
        logger.info("=" * 50)
        logger.info("[MOCK CALLBACK EXECUTION]")
        logger.info(f"Lead ID: {callback.lead_id}")
        logger.info(f"Scheduled Time: {callback.scheduled_at} ({callback.timezone})")
        logger.info("Status: EXECUTED")
        logger.info("=" * 50)

        # Update database status
        callback.status = "EXECUTED"
        db.commit()

    except Exception as e:
        logger.error(f"Error executing callback job: {e}")
        try:
            callback = db.query(ScheduledCallback).filter(ScheduledCallback.id == callback_db_id).first()
            if callback:
                callback.status = "FAILED"
                db.commit()
        except Exception as db_err:
            logger.error(f"Failed to update callback status to FAILED in DB: {db_err}")
    finally:
        db.close()


class SchedulerService:
    def __init__(self):
        self.scheduler = scheduler

    def schedule_callback(self, db: Session, callback_id: int) -> bool:
        """
        Schedules a callback job with APScheduler.
        If a job already exists for this lead, cancels it first to prevent duplicates.
        """
        callback = db.query(ScheduledCallback).filter(ScheduledCallback.id == callback_id).first()
        if not callback:
            logger.error(f"Failed to schedule: Callback ID {callback_id} not found.")
            return False

        # 1. Prevent duplicate scheduled jobs for the same lead
        self.cancel_active_callbacks_for_lead(db, callback.lead_id, exclude_id=callback_id)

        # 2. Check if scheduled_at is in the past
        tz = pytz.timezone(callback.timezone)
        now = datetime.now(tz)
        scheduled_time = tz.localize(callback.scheduled_at) if callback.scheduled_at.tzinfo is None else callback.scheduled_at.astimezone(tz)
        
        if scheduled_time < now:
            logger.warning(f"Scheduled time {scheduled_time} is in the past. Executing mock job immediately.")
            # Execute immediately in background
            self.scheduler.add_job(
                execute_callback_job,
                args=[callback.id],
                id=f"lead_{callback.lead_id}_immediate"
            )
            return True

        # 3. Schedule the job
        job_id = f"callback_{callback.id}"
        self.scheduler.add_job(
            execute_callback_job,
            trigger="date",
            run_date=scheduled_time,
            args=[callback.id],
            id=job_id,
            replace_existing=True
        )
        logger.info(f"Successfully scheduled callback job {job_id} for Lead {callback.lead_id} at {scheduled_time}")
        return True

    def cancel_callback(self, db: Session, callback_id: int) -> bool:
        """
        Cancels a scheduled callback job and updates its database status to CANCELLED.
        """
        callback = db.query(ScheduledCallback).filter(ScheduledCallback.id == callback_id).first()
        if not callback:
            return False

        # Remove from APScheduler if present
        job_id = f"callback_{callback_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed job {job_id} from APScheduler active queue.")

        callback.status = "CANCELLED"
        db.commit()
        logger.info(f"Callback ID {callback_id} status updated to CANCELLED.")
        return True

    def cancel_active_callbacks_for_lead(self, db: Session, lead_id: int, exclude_id: Optional[int] = None):
        """
        Cancels all active/scheduled callbacks for a lead.
        """
        query = db.query(ScheduledCallback).filter(
            ScheduledCallback.lead_id == lead_id,
            ScheduledCallback.status == "SCHEDULED"
        )
        if exclude_id is not None:
            query = query.filter(ScheduledCallback.id != exclude_id)
            
        active_callbacks = query.all()
        for cb in active_callbacks:
            job_id = f"callback_{cb.id}"
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            cb.status = "CANCELLED"
            logger.info(f"Cancelled duplicate/older scheduled callback ID {cb.id} for lead {lead_id}.")
        db.commit()
