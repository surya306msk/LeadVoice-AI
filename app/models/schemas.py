from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class HealthResponse(BaseModel):
    status: str

class StartCallRequest(BaseModel):
    phone_number: str

class StartCallResponse(BaseModel):
    status: str
    call_id: str

class LeadBase(BaseModel):
    customer_name: Optional[str] = None
    phone_number: str
    detected_language: Optional[str] = None
    business_type: Optional[str] = None
    products_sold: Optional[str] = None
    approximate_product_count: Optional[int] = None
    budget: Optional[str] = None
    timeline: Optional[str] = None
    required_features: Optional[str] = None
    decision_maker: Optional[str] = None
    objections_or_barriers: Optional[str] = None
    callback_request: Optional[str] = None
    callback_date_time: Optional[datetime] = None
    buying_intent: Optional[str] = None
    lead_classification: str = "COLD"
    reason_for_classification: Optional[str] = None
    conversation_summary: Optional[str] = None

class LeadResponse(LeadBase):
    id: int
    whatsapp_sent: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Phase 2 Schemas
from typing import Literal

class LeadAnalysis(BaseModel):
    language: Optional[str] = None
    business_type: Optional[str] = None
    products: Optional[str] = None
    product_count: Optional[int] = None
    budget: Optional[str] = None
    timeline: Optional[str] = None
    features: List[str] = []
    decision_maker: Optional[str] = None
    barrier: Optional[str] = None
    callback_requested: bool = False
    callback_expression: Optional[str] = None
    lead_status: Literal["HOT", "WARM", "COLD"]
    confidence: float
    reason: str
    recommended_action: Literal["NONE", "SEND_WHATSAPP_NOW", "SCHEDULE_CALLBACK", "SEND_FOLLOWUP"]
    conversation_summary: str

class AnalyzeLeadRequest(BaseModel):
    conversation: str
    existing_lead_data: Optional[dict] = None

class AnalyzeLeadResponse(BaseModel):
    analysis: LeadAnalysis
    source: str  # 'mock' or 'groq'


# Phase 3 Schemas
class CallbackParseRequest(BaseModel):
    callback_expression: str
    reference_time: Optional[datetime] = None

class CallbackParseResponse(BaseModel):
    callback_requested: bool
    original_expression: str
    scheduled_at: Optional[datetime] = None
    timezone: str = "Asia/Kolkata"
    confidence: float
    assumption: Optional[str] = None

class CallbackScheduleRequest(BaseModel):
    lead_id: int
    call_id: Optional[str] = None
    callback_expression: str

class CallbackResponse(BaseModel):
    callback_id: int
    lead_id: int
    call_id: Optional[str] = None
    original_expression: str
    scheduled_at: Optional[datetime] = None
    timezone: str
    status: str
    assumption: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Phase 4 Schemas
class MessagingTestRequest(BaseModel):
    provider: Optional[str] = None
    recipient: Optional[str] = None
    message: Optional[str] = "Test messaging provider"
    file_path: Optional[str] = None
    msg_type: Optional[str] = "text"  # text, document, image

class ProcessLeadActionRequest(BaseModel):
    lead_id: Optional[int] = None
    call_id: Optional[str] = None
    conversation: Optional[str] = None
    analysis: Optional[LeadAnalysis] = None
    provider: Optional[str] = None
    recipient: Optional[str] = None

class ActionProcessResponse(BaseModel):
    success: bool
    already_processed: bool = False
    status: str
    lead_id: Optional[int] = None
    classification: Optional[str] = None
    action_taken: Optional[str] = None
    provider: Optional[str] = None
    event_id: Optional[int] = None
    provider_message_id: Optional[str] = None
    message: Optional[str] = None
    attachments: Optional[dict] = {}
    error: Optional[str] = None

class WhatsAppFollowupRequest(BaseModel):
    lead_id: int
    custom_message: Optional[str] = None
    provider: Optional[str] = None


# Phase 5 Schemas
from typing import Dict, Any

class StartMockCallRequest(BaseModel):
    phone_number: str
    customer_name: Optional[str] = None
    language: Optional[str] = None
    provider: Optional[str] = None

class StartMockCallResponse(BaseModel):
    call_id: str
    lead_id: Optional[int] = None
    phone_number: str
    status: str
    greeting: str
    message: str

class MockCallMessageRequest(BaseModel):
    call_id: str
    message: str

class MockCallMessageResponse(BaseModel):
    call_id: str
    agent_response: str
    language: str
    classification: str
    action_triggered: Optional[str] = None
    lead_analysis: Dict[str, Any]

class EndMockCallRequest(BaseModel):
    call_id: str

class EndMockCallResponse(BaseModel):
    call_id: str
    status: str
    duration_seconds: Optional[int] = None
    lead_id: Optional[int] = None
    classification: Optional[str] = None
    followup_status: Optional[str] = None
    summary: Optional[str] = None


# Voice Webhook Schemas
class VoiceWebhookRequest(BaseModel):
    event_type: str  # call_started, transcript, call_ended
    call_id: Optional[str] = None
    phone_number: Optional[str] = None
    customer_name: Optional[str] = None
    speaker: Optional[str] = "customer"
    message: Optional[str] = None
    provider: Optional[str] = "retell"
    raw_payload: Optional[Dict[str, Any]] = None





