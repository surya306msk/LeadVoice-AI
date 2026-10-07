# LeadVoice AI — System Architecture Document

## 1. System Overview
LeadVoice AI is an intelligent multilingual voice agent designed to qualify inbound and outbound sales leads, extract business requirements during natural spoken conversations, perform real-time intent classification (`HOT`, `WARM`, `COLD`), trigger mid-call alert actions, schedule callbacks, and execute personalized follow-up messaging.

---

## 2. Component Architecture

```mermaid
graph TB
    subgraph Lead / Prospect
        Lead[Lead / Sales Prospect]
    end

    subgraph Telephony & Voice Provider Layer
        MockVoice[Mock Voice Service - Local / Dev]
        RetellVoice[Retell Voice Service - Production Abstraction]
        VoiceFactory[Voice Factory]
        Webhook[Voice Webhook Endpoint /api/voice/webhook]
    end

    subgraph Conversation & Intelligence Layer
        ConvEngine[Conversation Engine / Session Manager]
        LLMService[LLM / Lead Analysis Engine - Groq / Mock]
        Classification[Lead Classification Logic HOT / WARM / COLD]
    end

    subgraph Action & Messaging Layer
        ActionService[Action Service Engine]
        WASvc[WhatsApp Service - Production Required Provider]
        TelegramSvc[Telegram Service - Dev / Test Provider]
        FollowupSvc[Follow-up Action Service]
        CBParser[Callback Parser Service]
        Scheduler[Callback Scheduler - APScheduler]
    end

    subgraph Database Layer
        Database[(SQLite Database)]
    end

    Lead --> VoiceFactory
    MockVoice --> VoiceFactory
    RetellVoice --> VoiceFactory
    Webhook --> ConvEngine
    VoiceFactory --> ConvEngine

    ConvEngine --> LLMService
    LLMService --> Classification
    Classification --> ActionService

    ActionService --> WASvc
    ActionService --> TelegramSvc
    ActionService --> FollowupSvc
    ActionService --> CBParser
    CBParser --> Scheduler

    ConvEngine --> Database
    ActionService --> Database
    Scheduler --> Database
```

---

## 3. Provider Abstraction Scoping
- **Voice Providers**:
  - `MockVoiceService`: Local zero-cost testing without external dependencies.
  - `RetellVoiceService`: Telephony integration provider abstraction for production voice streaming.
- **Messaging Providers**:
  - `WhatsAppService`: Production-required messaging provider (Meta WhatsApp Cloud API abstraction).
  - `TelegramService`: Free development and testing messaging provider.

---

## 4. Conversation & Intelligence Flow

```mermaid
sequenceDiagram
    autonumber
    actor Prospect as Lead / Prospect
    participant Telephony as Voice Provider (Mock / Retell)
    participant Session as Conversation Engine
    participant LLM as LLM / Lead Analysis
    participant Action as Action Service
    participant Msg as Messaging Provider (WhatsApp / Telegram)

    Prospect->>Telephony: Spoken Speech Turn
    Telephony->>Session: process_user_turn(call_id, message)
    Session->>Database: Record Customer TranscriptLine
    Session->>LLM: analyze_conversation(full_transcript, existing_lead_data)
    LLM-->>Session: LeadAnalysis (progressive facts & status)
    Session->>Database: Update Lead (classification, budget, timeline, etc.)
    
    alt Status is HOT
        Session->>Action: process_lead_action(lead_id, analysis)
        Action->>Action: Check Idempotency (whatsapp_events)
        alt Not Processed
            Action->>Msg: send_message(HOT Lead Alert)
            Action->>Database: Save WhatsAppEvent (MOCK_SENT / SENT)
        end
    else Status is WARM & Callback Requested
        Session->>CBParser: parse_callback(expression)
        CBParser-->>Session: scheduled_at (IST)
        Session->>Database: Schedule Callback (ScheduledCallback)
    end

    Session-->>Telephony: Agent Spoken Response
    Telephony-->>Prospect: Spoken Speech Response
```

---

## 5. Lead Classification Rules
- **HOT**: Customer demonstrates high buying intent, explicit budget, defined launch timeline, and product specifications (`recommended_action`: `SEND_WHATSAPP_NOW`).
- **WARM**: Prospect expresses interest but presents an objection/barrier (e.g. partner discussion, budget review) or requests a callback (`recommended_action`: `SCHEDULE_CALLBACK`).
- **COLD**: Casual inquiry, general exploration, or lack of immediate timeline/budget (`recommended_action`: `SEND_FOLLOWUP`).

---

## 6. Database Entity Relationship Model

```mermaid
erDiagram
    LEADS ||--o{ CALLS : "makes"
    LEADS ||--o{ SCHEDULED_CALLBACKS : "has"
    LEADS ||--o{ WHATSAPP_EVENTS : "receives"
    CALLS ||--o{ TRANSCRIPTS : "contains"

    LEADS {
        int id PK
        string customer_name
        string phone_number
        string detected_language
        string business_type
        string products_sold
        int approximate_product_count
        string budget
        string timeline
        string lead_classification
        string reason_for_classification
        boolean whatsapp_sent
    }

    CALLS {
        int id PK
        string call_id UK
        string phone_number
        string status
        string detected_language
        datetime start_time
        datetime end_time
        int duration
        int lead_id FK
    }

    TRANSCRIPTS {
        int id PK
        string call_id FK
        string speaker
        string text
        string language
        datetime timestamp
    }

    SCHEDULED_CALLBACKS {
        int id PK
        int lead_id FK
        string call_id FK
        string original_expression
        datetime scheduled_at
        string timezone
        string status
    }

    WHATSAPP_EVENTS {
        int id PK
        int lead_id FK
        string call_id FK
        string provider
        string event_type
        string recipient
        string message
        string status
        string provider_message_id
    }
```

---

## 7. Deployment Architecture
- **Containerization**: Docker lightweight Linux container based on `python:3.10-slim`.
- **Process Manager**: Uvicorn ASGI server running FastAPI application on port 8000.
- **Database**: Embedded SQLite file-backed database with `init_db()` dynamic schema reflection.
- **Background Engine**: APScheduler in-process background scheduler.
