import uvicorn
from fastapi import FastAPI
from app.core.config import settings
from app.core.logging import logger
from app.database.database import engine, Base, init_db
from app.models import database_models
from app.api import health, leads, callbacks, actions, voice
from app.services.scheduler_service import scheduler

# Create DB tables (simplest method for SQLite setup)
logger.info("Initializing database tables...")
init_db()
logger.info("Database tables initialized successfully.")

app = FastAPI(
    title="LeadVoice AI",
    description="Intelligent Multilingual Voice Agent for Lead Qualification and Real-Time Sales Automation",
    version="1.0.0"
)

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "code": f"HTTP_{exc.status_code}"
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": "Request validation failed",
            "details": exc.errors(),
            "code": "VALIDATION_ERROR"
        }
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server exception on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "An internal server error occurred.",
            "code": "INTERNAL_SERVER_ERROR"
        }
    )

# Include routers
app.include_router(health.router)
app.include_router(leads.router)
app.include_router(callbacks.router)
app.include_router(actions.router)
app.include_router(voice.router)

@app.on_event("startup")
async def startup_event():
    # Start the APScheduler
    logger.info("Starting background scheduler...")
    scheduler.start()
    logger.info("Background scheduler started successfully.")
    
    logger.info("=" * 50)
    logger.info("LeadVoice AI Application Startup")
    logger.info(f"Host: {settings.HOST} | Port: {settings.PORT}")
    logger.info(f"MOCK_MODE: {settings.MOCK_MODE}")
    logger.info(f"Database URL: {settings.DATABASE_URL}")
    logger.info("=" * 50)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down background scheduler...")
    scheduler.shutdown()
    logger.info("Background scheduler shut down.")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
