# LeadVoice AI — Evaluator Demonstration Script

This document provides a concise 3–5 minute step-by-step walkthrough for evaluating LeadVoice AI during an interview or assignment code review.

---

## 1. Project Introduction (30 seconds)
LeadVoice AI is an outbound voice agent & lead-qualification platform designed to automate initial sales calls, extract key buying signals (budget, timeline, product count, decision maker, barriers), classify leads (HOT, WARM, COLD), schedule follow-up callbacks, and trigger automated messaging actions via WhatsApp (production abstraction) and Telegram (free development provider).

Key Highlights:
- **Cost-free local execution**: Powered by `MOCK_MODE=true` without requiring paid APIs (Retell, Groq, Twilio).
- **Comprehensive test suite**: 61 automated tests covering end-to-end functionality.
- **Privacy & Security**: Built-in phone number and API key masking in application logs.

---

## 2. Architecture Overview (30 seconds)
LeadVoice AI follows a modular, decoupled architecture:
1. **Voice Layer**: Voice provider abstraction supporting `MockVoiceService` and `RetellVoiceService` with a unified `/api/voice/webhook`.
2. **Conversation Engine**: Manages multi-turn conversation state, transcript persistence, and progressive lead intelligence extraction.
3. **LLM & Analysis Engine**: Groq API interface with fallback deterministic local mock analyzer.
4. **Action Engine & Messaging Abstraction**: Executes real-time actions (`HOT_LEAD_ALERT`, `POST_CALL_FOLLOWUP`, document attachments) via WhatsApp Cloud API (production requirement) or Telegram Bot API (dev/test provider).
5. **Callback Scheduler**: Uses `APScheduler` to parse natural language expressions ("tomorrow morning", "next Monday at 3 PM") into UTC timestamps and store scheduled jobs.
6. **Database Persistence**: SQLite database storing leads, calls, transcripts, callbacks, and messaging audit events.

---

## 3. HOT Lead Demonstration (45 seconds)
Execute the deterministic HOT lead demo:
```bash
.venv\Scripts\python scratch/demo_hot.py
```
What to observe:
- **Product & Requirement Discovery**: Customer mentions catalog size (500 products) and e-commerce requirement.
- **Budget & Timeline**: Customer defines budget (100,000 INR) and urgent timeline (3 weeks).
- **Decision Maker**: Customer confirms sole decision-making authority.
- **Classification**: Lead status transitions to **HOT**.
- **Action Trigger**: Action service fires a `HOT_LEAD_ALERT` messaging event safely in `MOCK_MODE`.

---

## 4. WARM Lead Demonstration (45 seconds)
Execute the deterministic WARM lead demo:
```bash
.venv\Scripts\python scratch/demo_warm.py
```
What to observe:
- **Barrier Extraction**: Customer expresses interest but states a barrier ("need to discuss budget with business partner").
- **Callback Request**: Customer requests "Call me tomorrow morning".
- **Classification**: Lead status is evaluated as **WARM**.
- **Database Insertion**: The barrier is saved under `objections_or_barriers` and a callback job is scheduled in the database via `APScheduler`.

---

## 5. COLD Lead Demonstration (30 seconds)
Execute the deterministic COLD lead demo:
```bash
.venv\Scripts\python scratch/demo_cold.py
```
What to observe:
- **Low Buying Intent**: Customer indicates "just exploring options, not looking to buy or build right now".
- **No Invented Data**: Unmentioned fields (budget, timeline) remain `None`.
- **Classification**: Lead is classified as **COLD**.
- **Safe Handling**: No HOT lead alerts or urgent callbacks are triggered. Basic follow-up recommendation is logged.

---

## 6. Multilingual Demonstration (30 seconds)
Execute the multilingual demo script:
```bash
.venv\Scripts\python scratch/demo_multilingual.py
```
What to observe:
- Demonstrates natural conversational flow in **English**, **Hindi / Hinglish**, and **Telugu / Teluglish**.
- Shows turn-by-turn language detection, extracted intelligence, and sales-consultative agent responses tailored to the detected language.

---

## 7. Callback Scheduling (15 seconds)
Show the natural-language callback parser endpoint:
```bash
POST /api/callbacks/parse
{
  "callback_expression": "next Tuesday at 4 PM"
}
```
Response demonstrates ISO datetime interpretation, timezone assumption (`Asia/Kolkata`), and structured payload generation.

---

## 8. Messaging Action (15 seconds)
Demonstrate the provider abstraction by sending a test message:
```bash
POST /api/messaging/test
{
  "provider": "telegram",
  "recipient": "9353352276",
  "message": "Demo follow-up message from LeadVoice AI"
}
```
Displays safe MOCK message execution when live API tokens are omitted.

---

## 9. Explain MOCK_MODE (15 seconds)
- When `MOCK_MODE=true` in `.env`, the system runs completely locally without external API keys or telephony charges.
- Mock providers simulate voice turns, LLM analyses, and messaging delivery while testing 100% of internal state, database persistence, and action triggers.

---

## 10. Explain Real-Provider Readiness (15 seconds)
- **Voice**: `RetellVoiceService` is implemented and selectable via `VOICE_PROVIDER=retell`. Webhook `/api/voice/webhook` is ready to accept production telephony callbacks.
- **Messaging**: `WhatsAppService` is implemented for Meta Cloud API (`MESSAGING_PROVIDER=whatsapp`). Telegram is available for zero-cost development testing.

---

## 11. Limitations & Scope (15 seconds)
- **In-Process Scheduler**: APScheduler runs in-process with SQLite; horizontal scaling across multiple instances requires Redis / Celery.
- **Live Verification**: Retell and Meta WhatsApp Cloud API integrations are integration-ready but not live-validated against paid production accounts in this test environment.
