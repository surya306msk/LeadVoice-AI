"""Regression tests for the mock lead-analysis pipeline (LLMService._mock_analysis)."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.llm_service import LLMService

client = TestClient(app)


async def _analyze(conversation: str, existing_lead_data=None):
    return await LLMService().analyze_conversation(conversation, existing_lead_data)


# ---------------------------------------------------------------------------
# Test inputs
# ---------------------------------------------------------------------------

# Original bug-report input — split into natural turns joined as a transcript
# so the test stays readable without one giant paragraph.
REGRESSION_TURNS = "\n".join([
    "I need an e-commerce website for my business.",
    "Around 500 products.",
    "Budget is ₹1,00,000.",
    "Need it within 3 weeks.",
    "I'm the founder and decision maker.",
    "Ready to proceed soon.",
])

HOT_INPUT = (
    "I need an e-commerce website for 200 products. "
    "My budget is around one lakh and I need it within one month."
)

WARM_INPUT = (
    "I want an e-commerce website but I need to discuss the budget with my "
    "business partner. Please call me back tomorrow morning."
)

COLD_INPUT = (
    "I'm just checking what kind of websites you build. "
    "I don't have any immediate plans."
)

MISSING_BUDGET_INPUT = "I'm interested in an online clothing store but don't know my budget yet."

MISSING_TIMELINE_INPUT = "My budget is around 80000 rupees for 150 products. I haven't decided on a timeline."

VAGUE_INPUT = "Hello, I am interested, but I don't know the budget yet."

HINDI_INPUT = (
    "Mujhe ek online store chahiye. "
    "Mere paas 300 products hain. "
    "Budget ek lakh rupaye hai aur ek mahine mein chahiye."
)

TELUGU_INPUT = (
    "Naku oka e-commerce website kavali. "
    "500 products unnai. "
    "Budget oka lakh rupayalu. "
    "3 weeks lo complete cheyandi."
)


# ---------------------------------------------------------------------------
# 1. Regression: original failing conversation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_regression_failing_conversation():
    """Regression: multi-turn e-commerce input must classify as HOT with all fields extracted."""
    analysis = await _analyze(REGRESSION_TURNS)

    assert analysis.business_type is not None
    assert "commerce" in analysis.business_type.lower()
    assert analysis.product_count == 500
    assert analysis.products is not None
    assert analysis.budget is not None and "100000" in analysis.budget
    assert analysis.timeline is not None and "3" in analysis.timeline
    assert analysis.decision_maker is not None
    assert analysis.lead_status == "HOT"
    assert analysis.recommended_action == "SEND_WHATSAPP_NOW"
    assert analysis.reason != "Initial baseline classification."


def test_api_regression_failing_conversation():
    """Same regression via HTTP endpoint."""
    response = client.post("/api/analyze-lead", json={"conversation": REGRESSION_TURNS})
    assert response.status_code == 200
    a = response.json()["analysis"]
    assert a["business_type"] is not None
    assert a["product_count"] == 500
    assert a["budget"] is not None and "100000" in a["budget"]
    assert a["timeline"] is not None and "3" in a["timeline"]
    assert a["lead_status"] == "HOT"
    assert a["recommended_action"] == "SEND_WHATSAPP_NOW"
    assert a["reason"] != "Initial baseline classification."


# ---------------------------------------------------------------------------
# 2. HOT lead
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hot_lead():
    analysis = await _analyze(HOT_INPUT)
    assert analysis.lead_status == "HOT"
    assert analysis.recommended_action == "SEND_WHATSAPP_NOW"
    assert analysis.product_count == 200
    assert analysis.budget == "100000 INR"
    assert analysis.timeline == "1 month"


def test_api_hot_lead():
    response = client.post("/api/analyze-lead", json={"conversation": HOT_INPUT})
    assert response.status_code == 200
    data = response.json()["analysis"]
    assert data["lead_status"] == "HOT"
    assert data["recommended_action"] == "SEND_WHATSAPP_NOW"


# ---------------------------------------------------------------------------
# 3. WARM lead – barrier + callback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_warm_lead_with_barrier_and_callback():
    analysis = await _analyze(WARM_INPUT)
    assert analysis.lead_status == "WARM"
    assert analysis.recommended_action == "SCHEDULE_CALLBACK"
    assert analysis.callback_requested is True
    assert analysis.callback_expression == "tomorrow morning"
    assert analysis.barrier is not None
    assert "partner" in analysis.barrier.lower() or "approval" in analysis.barrier.lower()


def test_api_warm_lead():
    response = client.post("/api/analyze-lead", json={"conversation": WARM_INPUT})
    assert response.status_code == 200
    data = response.json()["analysis"]
    assert data["lead_status"] == "WARM"
    assert data["callback_requested"] is True
    assert data["callback_expression"] == "tomorrow morning"


# ---------------------------------------------------------------------------
# 4. COLD lead
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cold_lead():
    analysis = await _analyze(COLD_INPUT)
    assert analysis.lead_status == "COLD"
    assert analysis.recommended_action == "SEND_FOLLOWUP"


def test_api_cold_lead():
    response = client.post("/api/analyze-lead", json={"conversation": COLD_INPUT})
    assert response.status_code == 200
    data = response.json()["analysis"]
    assert data["lead_status"] == "COLD"
    assert data["recommended_action"] == "SEND_FOLLOWUP"


# ---------------------------------------------------------------------------
# 5. Missing budget – no hallucination
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_budget_no_hallucination():
    analysis = await _analyze(MISSING_BUDGET_INPUT)
    assert analysis.budget is None, f"budget must be null when not mentioned; got: {analysis.budget}"


def test_api_missing_budget():
    response = client.post("/api/analyze-lead", json={"conversation": MISSING_BUDGET_INPUT})
    assert response.status_code == 200
    assert response.json()["analysis"]["budget"] is None


# ---------------------------------------------------------------------------
# 6. Missing timeline – no hallucination
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_timeline_no_hallucination():
    analysis = await _analyze(MISSING_TIMELINE_INPUT)
    assert analysis.budget is not None
    assert analysis.timeline is None, f"timeline must be null when not mentioned; got: {analysis.timeline}"


def test_api_missing_timeline():
    response = client.post("/api/analyze-lead", json={"conversation": MISSING_TIMELINE_INPUT})
    assert response.status_code == 200
    a = response.json()["analysis"]
    assert a["budget"] is not None
    assert a["timeline"] is None


# ---------------------------------------------------------------------------
# 7. Progressive multi-turn extraction  (COLD → products → budget/timeline → HOT)
# ---------------------------------------------------------------------------

def test_api_multi_turn_progressive_extraction():
    r1 = client.post("/api/analyze-lead", json={"conversation": "I'm just exploring options."})
    assert r1.status_code == 200
    assert r1.json()["analysis"]["lead_status"] == "COLD"

    existing = r1.json()["analysis"]
    r2 = client.post(
        "/api/analyze-lead",
        json={"conversation": "I actually have around 300 products.", "existing_lead_data": existing},
    )
    assert r2.status_code == 200
    assert r2.json()["analysis"]["product_count"] == 300

    existing2 = r2.json()["analysis"]
    r3 = client.post(
        "/api/analyze-lead",
        json={
            "conversation": "My budget is around one lakh and I want to launch next month.",
            "existing_lead_data": existing2,
        },
    )
    assert r3.status_code == 200
    s3 = r3.json()["analysis"]
    assert s3["lead_status"] == "HOT"
    assert s3["recommended_action"] == "SEND_WHATSAPP_NOW"
    assert s3["product_count"] == 300    # preserved from turn 2
    assert s3["budget"] == "100000 INR"


# ---------------------------------------------------------------------------
# 8. No hallucination – vague input
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_hallucination_vague_input():
    analysis = await _analyze(VAGUE_INPUT)
    assert analysis.budget is None
    assert analysis.timeline is None
    assert analysis.product_count is None


def test_api_no_hallucination_vague():
    response = client.post("/api/analyze-lead", json={"conversation": VAGUE_INPUT})
    assert response.status_code == 200
    a = response.json()["analysis"]
    assert a["budget"] is None
    assert a["timeline"] is None
    assert a["product_count"] is None


# ---------------------------------------------------------------------------
# 9. Hindi / Hinglish
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hindi_hinglish_support():
    analysis = await _analyze(HINDI_INPUT)
    assert analysis.language in ("Hindi", "English")
    assert analysis.product_count == 300
    assert analysis.budget == "100000 INR"
    assert analysis.timeline == "1 month"
    assert analysis.lead_status == "HOT"


# ---------------------------------------------------------------------------
# 10. Telugu / Teluglish
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_telugu_teluglish_support():
    analysis = await _analyze(TELUGU_INPUT)
    assert analysis.language in ("Telugu", "English")
    assert analysis.product_count == 500
    assert analysis.budget == "100000 INR"
    assert analysis.timeline is not None and "3" in analysis.timeline


# ---------------------------------------------------------------------------
# 11. API sanity checks
# ---------------------------------------------------------------------------

def test_api_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_api_empty_conversation_returns_400():
    response = client.post("/api/analyze-lead", json={"conversation": ""})
    assert response.status_code == 400


def test_api_returns_mock_source():
    response = client.post("/api/analyze-lead", json={"conversation": REGRESSION_TURNS})
    assert response.status_code == 200
    assert response.json()["source"] == "mock"
