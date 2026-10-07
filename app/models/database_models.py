from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.database import Base

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, nullable=True)
    phone_number = Column(String, index=True, nullable=False)
    detected_language = Column(String, nullable=True)
    business_type = Column(String, nullable=True)
    products_sold = Column(String, nullable=True)
    approximate_product_count = Column(Integer, nullable=True)
    budget = Column(String, nullable=True)
    timeline = Column(String, nullable=True)
    required_features = Column(Text, nullable=True)  # JSON or comma-separated string
    decision_maker = Column(String, nullable=True)
    objections_or_barriers = Column(Text, nullable=True)
    callback_request = Column(String, nullable=True)
    callback_date_time = Column(DateTime, nullable=True)
    buying_intent = Column(String, nullable=True)
    lead_classification = Column(String, default="COLD")  # HOT, WARM, COLD
    reason_for_classification = Column(Text, nullable=True)
    conversation_summary = Column(Text, nullable=True)
    
    # Flags and tracking
    whatsapp_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    calls = relationship("Call", back_populates="lead")
    callbacks = relationship("ScheduledCallback", back_populates="lead")
    whatsapp_events = relationship("WhatsAppEvent", back_populates="lead")


class Call(Base):
    __tablename__ = "calls"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(String, unique=True, index=True, nullable=False)  # Retell call ID or generated ID
    phone_number = Column(String, nullable=False)
    status = Column(String, default="INITIATED")  # INITIATED, IN_PROGRESS, COMPLETED, FAILED
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    duration = Column(Integer, nullable=True)  # duration in seconds
    detected_language = Column(String, nullable=True)
    
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True)
    lead = relationship("Lead", back_populates="calls")
    transcripts = relationship("TranscriptLine", back_populates="call")


class TranscriptLine(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(String, ForeignKey("calls.call_id"), nullable=False)
    speaker = Column(String, nullable=False)  # agent or customer
    text = Column(Text, nullable=False)
    language = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    call = relationship("Call", back_populates="transcripts")


class ScheduledCallback(Base):
    __tablename__ = "scheduled_callbacks"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    call_id = Column(String, ForeignKey("calls.call_id"), nullable=True)
    original_expression = Column(String, nullable=False)
    scheduled_at = Column(DateTime, nullable=True)  # Nullable if ambiguous
    timezone = Column(String, default="Asia/Kolkata")
    status = Column(String, default="SCHEDULED")  # SCHEDULED, EXECUTED, CANCELLED, FAILED
    assumption = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lead = relationship("Lead", back_populates="callbacks")


class WhatsAppEvent(Base):
    __tablename__ = "whatsapp_events"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    call_id = Column(String, ForeignKey("calls.call_id"), nullable=True)
    provider = Column(String, default="telegram")  # telegram, whatsapp, mock
    event_type = Column(String, nullable=True)    # HOT_LEAD_ALERT, POST_CALL_FOLLOWUP, RESUME_ATTACHMENT, ARCHITECTURE_ATTACHMENT
    recipient = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)   # alias/compatibility
    message_type = Column(String, nullable=True)   # alias/compatibility
    message = Column(Text, nullable=True)
    content = Column(Text, nullable=True)          # alias/compatibility
    status = Column(String, default="PENDING")     # PENDING, SENT, FAILED, MOCK_SENT
    provider_message_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lead = relationship("Lead", back_populates="whatsapp_events")

