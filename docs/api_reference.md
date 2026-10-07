# LeadVoice AI — API Reference

This document provides a comprehensive reference of all active REST API endpoints implemented in LeadVoice AI.

---

## 1. Health Endpoints

### `GET /health`
- **Purpose**: Lightweight health check returning application status.
- **Example Response**:
```json
{
  "status": "healthy"
}
```

### `GET /health/ready`
- **Purpose**: Verifies database connection, configuration state, and MOCK_MODE readiness without invoking external paid APIs.
- **Example Response**:
```json
{
  "status": "ready",
  "database": "connected",
  "mock_mode": true,
  "voice_provider": "mock",
  "messaging_provider": "telegram"
}
```

---

## 2. Voice Endpoints

### `POST /api/voice/mock/start`
- **Purpose**: Initiates a mock voice call session.
- **Request Body**:
```json
{
  "phone_number": "9353352276",
  "customer_name": "Surya",
  "language": "English",
  "provider": "mock"
}
```
- **Example Response**:
```json
{
  "call_id": "call_a1b2c3d4e5f6",
  "phone_number": "9353352276",
  "status": "IN_PROGRESS",
  "greeting": "Hello! Thank you for calling LeadVoice AI. How can I help you today?"
}
```

### `POST /api/voice/mock/message`
- **Purpose**: Processes a single conversation turn from the user during an active mock call.
- **Request Body**:
```json
{
  "call_id": "call_a1b2c3d4e5f6",
  "message": "I need an e-commerce website for my clothing business."
}
```
- **Example Response**:
```json
{
  "call_id": "call_a1b2c3d4e5f6",
  "agent_response": "Absolutely! What kind of business do you run, and what products do you plan to list?",
  "language": "English",
  "classification": "HOT",
  "action_triggered": "HOT_LEAD_ALERT",
  "lead_analysis": {
    "product_count": 500,
    "budget": "100000 INR",
    "timeline": "1 month",
    "lead_status": "HOT"
  }
}
```

### `POST /api/voice/mock/end`
- **Purpose**: Ends an active mock voice call session.
- **Request Body**:
```json
{
  "call_id": "call_a1b2c3d4e5f6"
}
```
- **Example Response**:
```json
{
  "call_id": "call_a1b2c3d4e5f6",
  "status": "COMPLETED",
  "duration": 45,
  "summary": "Customer requested e-commerce website with 500 products."
}
```

### `POST /api/voice/webhook`
- **Purpose**: Unified webhook endpoint for production voice providers (e.g. Retell, Twilio).
- **Request Body**:
```json
{
  "event_type": "transcript",
  "call_id": "retell_call_123",
  "phone_number": "9353352276",
  "customer_name": "Surya",
  "message": "Call me tomorrow morning."
}
```
- **Example Response**:
```json
{
  "success": true,
  "event": "transcript",
  "data": {
    "call_id": "retell_call_123",
    "agent_response": "I have scheduled a callback for tomorrow morning.",
    "classification": "WARM"
  }
}
```

### `GET /api/voice/calls/{call_id}`
- **Purpose**: Retrieves call details and full conversation transcript lines for a specific call ID.
- **Example Response**:
```json
{
  "call_id": "call_a1b2c3d4e5f6",
  "phone_number": "9353352276",
  "status": "COMPLETED",
  "transcripts": [
    {"speaker": "agent", "text": "Hello! Thank you for calling..."},
    {"speaker": "customer", "text": "I need an e-commerce website..."}
  ]
}
```

---

## 3. Leads Endpoints

### `POST /api/analyze-lead`
- **Purpose**: Analyzes conversation transcript text using LLM (Groq API or deterministic mock analyzer) to extract lead intelligence.
- **Request Body**:
```json
{
  "conversation": "AGENT: How can I help?\nCUSTOMER: I sell footwear and need an e-commerce site for 200 items.",
  "existing_lead_data": null
}
```
- **Example Response**:
```json
{
  "analysis": {
    "language": "English",
    "business_type": "Footwear",
    "product_count": 200,
    "budget": null,
    "timeline": null,
    "lead_status": "COLD",
    "confidence": 0.95,
    "recommended_action": "SEND_FOLLOWUP"
  },
  "source": "mock"
}
```

---

## 4. Callbacks Endpoints

### `POST /api/callbacks/parse`
- **Purpose**: Parses natural-language date/time expressions into structured ISO timestamps.
- **Request Body**:
```json
{
  "callback_expression": "tomorrow morning at 10 AM",
  "reference_time": "2026-10-07T10:00:00Z"
}
```
- **Example Response**:
```json
{
  "original_expression": "tomorrow morning at 10 AM",
  "scheduled_at": "2026-10-08T10:00:00Z",
  "timezone": "Asia/Kolkata",
  "assumption": "Parsed 'tomorrow morning at 10 AM' relative to reference time."
}
```

### `POST /api/callbacks/schedule`
- **Purpose**: Parses a natural callback expression and creates a scheduled callback job for a lead.
- **Request Body**:
```json
{
  "lead_id": 1,
  "call_id": "call_a1b2c3d4e5f6",
  "callback_expression": "tomorrow morning"
}
```
- **Example Response**:
```json
{
  "callback_id": 1,
  "lead_id": 1,
  "call_id": "call_a1b2c3d4e5f6",
  "original_expression": "tomorrow morning",
  "scheduled_at": "2026-10-08T10:00:00",
  "timezone": "Asia/Kolkata",
  "status": "SCHEDULED",
  "created_at": "2026-10-07T18:24:29"
}
```

### `GET /api/callbacks`
- **Purpose**: Returns a list of all scheduled callbacks in the database.

### `GET /api/callbacks/{callback_id}`
- **Purpose**: Retrieves details for a specific scheduled callback.

### `DELETE /api/callbacks/{callback_id}`
- **Purpose**: Cancels a scheduled callback job in APScheduler and updates database status to `CANCELLED`.

---

## 5. Messaging & Action Endpoints

### `POST /api/messaging/test`
- **Purpose**: Tests sending messages or file attachments (resume, architecture diagram) via selected provider (Telegram, WhatsApp, Mock).
- **Request Body**:
```json
{
  "provider": "telegram",
  "recipient": "9353352276",
  "message": "Hello from LeadVoice AI",
  "msg_type": "text"
}
```
- **Example Response**:
```json
{
  "status": "success",
  "provider": "telegram",
  "message_id": "mock_tg_msg_123"
}
```

### `POST /api/whatsapp/test`
- **Purpose**: Backward-compatible endpoint to test WhatsApp Cloud API messaging abstraction.

### `POST /api/actions/process-lead`
- **Purpose**: Triggers Action Engine logic (classification check, personalized message composition, WhatsApp/Telegram dispatch, callback scheduling, idempotency enforcement).
- **Request Body**:
```json
{
  "lead_id": 1,
  "call_id": "call_a1b2c3d4e5f6",
  "provider": "telegram"
}
```
- **Example Response**:
```json
{
  "status": "processed",
  "action_taken": "HOT_LEAD_ALERT",
  "messaging_event_id": 1
}
```

### `POST /api/whatsapp/followup`
- **Purpose**: Triggers an explicit follow-up message action for a specified lead ID.
