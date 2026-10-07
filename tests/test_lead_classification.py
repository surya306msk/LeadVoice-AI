import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.llm_service import LLMService

client = TestClient(app)

# Test inputs
HOT_INPUT = "I need an e-commerce website for 200 products. My budget is around one lakh and I need it within one month."
WARM_INPUT = "I want an e-commerce website but I need to discuss the budget with my business partner. Please call me tomorrow morning."
COLD_INPUT = "I'm just checking what kind of websites you build. I don't have any immediate plans."

@pytest.mark.asyncio
async def test_mock_mode_hot():
    llm_service = LLMService()
    # verify settings or fallback mock mode handles it
    analysis = await llm_service.analyze_conversation(HOT_INPUT)
    assert analysis.lead_status == "HOT"
    assert analysis.recommended_action == "SEND_WHATSAPP_NOW"
    assert analysis.product_count == 200
    assert analysis.budget == "100000 INR"
    assert analysis.timeline == "1 month"

@pytest.mark.asyncio
async def test_mock_mode_warm():
    llm_service = LLMService()
    analysis = await llm_service.analyze_conversation(WARM_INPUT)
    assert analysis.lead_status == "WARM"
    assert analysis.recommended_action == "SCHEDULE_CALLBACK"
    assert analysis.callback_requested is True
    assert analysis.callback_expression == "tomorrow morning"

@pytest.mark.asyncio
async def test_mock_mode_cold():
    llm_service = LLMService()
    analysis = await llm_service.analyze_conversation(COLD_INPUT)
    assert analysis.lead_status == "COLD"
    assert analysis.recommended_action == "SEND_FOLLOWUP"

def test_api_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_api_analyze_lead_endpoint_hot():
    response = client.post(
        "/api/analyze-lead",
        json={"conversation": HOT_INPUT}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "mock"
    assert data["analysis"]["lead_status"] == "HOT"
    assert data["analysis"]["recommended_action"] == "SEND_WHATSAPP_NOW"

def test_api_analyze_lead_endpoint_missing_info():
    response = client.post(
        "/api/analyze-lead",
        json={"conversation": "Hello, I am interested, but I don't know the budget yet."}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["analysis"]["budget"] is None

def test_api_analyze_lead_endpoint_empty():
    response = client.post(
        "/api/analyze-lead",
        json={"conversation": ""}
    )
    assert response.status_code == 400

def test_api_multi_turn_update():
    # Turn 1: COLD
    response1 = client.post(
        "/api/analyze-lead",
        json={"conversation": "I'm just exploring options."}
    )
    assert response1.status_code == 200
    res1 = response1.json()
    assert res1["analysis"]["lead_status"] == "COLD"
    
    # Turn 2: Provide product count
    existing_data = res1["analysis"]
    response2 = client.post(
        "/api/analyze-lead",
        json={
            "conversation": "I actually have around 300 products.",
            "existing_lead_data": existing_data
        }
    )
    assert response2.status_code == 200
    res2 = response2.json()
    assert res2["analysis"]["product_count"] == 300
    
    # Turn 3: Provide budget/timeline -> HOT
    existing_data2 = res2["analysis"]
    response3 = client.post(
        "/api/analyze-lead",
        json={
            "conversation": "My budget is around one lakh and I want to launch next month.",
            "existing_lead_data": existing_data2
        }
    )
    assert response3.status_code == 200
    res3 = response3.json()
    assert res3["analysis"]["lead_status"] == "HOT"
    assert res3["analysis"]["recommended_action"] == "SEND_WHATSAPP_NOW"
    assert res3["analysis"]["product_count"] == 300
    assert res3["analysis"]["budget"] == "100000 INR"
