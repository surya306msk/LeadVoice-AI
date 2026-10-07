# LeadVoice AI — Deployment Guide

This document provides instructions for deploying LeadVoice AI locally, in Docker containers, and on free/low-cost cloud container platforms (such as Render, Railway, Fly.io, or AWS App Runner).

---

## 1. Local Setup
To run LeadVoice AI locally for development and testing:

```bash
# 1. Clone repository
git clone <repository_url>
cd "LeadVoice AI"

# 2. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate   # On Windows
# source .venv/bin/activate  # On Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Initialize environment variables
copy .env.example .env

# 5. Start Uvicorn development server
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

---

## 2. Environment Variables
LeadVoice AI relies on key environment variables defined in `.env`:

| Variable | Recommended Default | Purpose |
| :--- | :--- | :--- |
| `PORT` | `8000` | Application HTTP server port (automatically set by cloud platforms) |
| `HOST` | `0.0.0.0` | Host binding interface for container networks |
| `MOCK_MODE` | `true` | Enables zero-cost local mock execution without external credentials |
| `VOICE_PROVIDER` | `mock` | Selects voice service implementation (`mock`, `retell`) |
| `MESSAGING_PROVIDER` | `telegram` | Selects messaging provider (`telegram`, `whatsapp`, `mock`) |
| `DATABASE_URL` | `sqlite:///./leadvoice.db` | SQLite database connection string |

---

## 3. MOCK_MODE Configuration
`MOCK_MODE=true` is the default deployment configuration.
In this mode:
- No paid third-party subscriptions (Retell AI, Meta WhatsApp Cloud API, Groq LLM) are required.
- The voice conversation engine processes spoken text turns deterministically.
- All lead classification rules (`HOT`, `WARM`, `COLD`), callback scheduling, database transactions, and messaging event logs execute completely and accurately.

---

## 4. Docker Deployment

### Building and Running Docker Image Locally
```bash
# Build lightweight Linux container
docker build -t leadvoice-ai .

# Run container in background
docker run -d -p 8000:8000 --name leadvoice-app --env MOCK_MODE=true leadvoice-ai
```

*(Note: Docker configuration has been verified; local execution depends on Docker Engine availability on the host environment).*

---

## 5. Generic Cloud Deployment Requirements
For free/low-cost cloud container platforms (e.g. Render, Railway, Fly.io):
1. **Build Method**: Select Dockerfile deployment.
2. **Port Binding**: Ensure your service reads the `$PORT` environment variable injected by the provider.
3. **Environment Variables**: Configure `MOCK_MODE=true`, `HOST=0.0.0.0`, `VOICE_PROVIDER=mock`, `MESSAGING_PROVIDER=telegram`.
4. **Health Check Path**: Point container health probes to `/health`.
5. **Database File**: For stateless containers, SQLite will initialize `leadvoice.db` in `/app`. For persistent memory across restarts, attach a persistent volume to `/app/leadvoice.db` or connect an external database.

---

## 6. Health Endpoint
- **URL Path**: `GET /health`
- **Response**: `{"status": "healthy"}`
- **Purpose**: Lightweight HTTP probe used by load balancers, Docker, and Kubernetes to confirm process responsiveness.

---

## 7. Readiness Endpoint
- **URL Path**: `GET /health/ready`
- **Response**:
```json
{
  "status": "ready",
  "database": "connected",
  "mock_mode": true,
  "voice_provider": "mock",
  "messaging_provider": "telegram"
}
```
- **Purpose**: Verifies SQLite database file accessibility and startup configuration state without invoking external paid APIs.

---

## 8. Production Limitations
- **Single-Instance SQLite**: SQLite is embedded and single-file backed. Horizontal multi-instance scaling requires an external SQL database (e.g., PostgreSQL).
- **In-Process Scheduler**: APScheduler runs inside the Uvicorn process. Distributed task execution across multiple servers requires a Celery/Redis queue architecture.

---

## 9. How to Verify Deployment
Once deployed to a server or local instance:
1. Verify container responsiveness:
   ```bash
   curl http://<deployment-host>:<port>/health
   ```
2. Verify readiness check:
   ```bash
   curl http://<deployment-host>:<port>/health/ready
   ```
3. Execute a mock call workflow:
   ```bash
   curl -X POST http://<deployment-host>:<port>/api/voice/mock/start \
     -H "Content-Type: application/json" \
     -d '{"phone_number": "9353352276", "customer_name": "Surya"}'
   ```

---

## 10. How to Configure Real Providers Later
To switch from `MOCK_MODE` to production providers when credentials are acquired:
1. **Groq LLM**: Set `MOCK_MODE=false` and provide `GROQ_API_KEY=<your_groq_key>`.
2. **Retell AI Voice**: Set `VOICE_PROVIDER=retell`, `RETELL_API_KEY=<your_key>`, and `RETELL_AGENT_ID=<your_agent_id>`. Point Retell webhooks to `POST /api/voice/webhook`.
3. **WhatsApp Cloud API**: Set `MESSAGING_PROVIDER=whatsapp`, `WHATSAPP_ACCESS_TOKEN=<token>`, `WHATSAPP_PHONE_NUMBER_ID=<id>`.
