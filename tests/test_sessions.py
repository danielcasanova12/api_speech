
import pytest
import pytest_asyncio
import uuid
from httpx import AsyncClient
from sqlalchemy.future import select

from database import get_async_session
from models import Dataset

# Re-use the async_client fixture from conftest.py

@pytest.fixture(scope="module")
def test_data():
    unique_id = uuid.uuid4()
    return {
        "user_data": {
            "email": f"testuser_sessions_{unique_id}@example.com",
            "password": "aVeryStrongPassword123",
            "nome_completo": "Session Test User",
            "data_nascimento": "1995-01-01",
            "genero": "female",
            "language": "pt-BR",
            "cidade_nascimento": {"cidade": "Sessionville", "estado": "SS"},
            "cidade_atual": {"cidade": "Sessionburg", "estado": "SS"},
            "historico_moradia": [{"periodo": "0-18 anos", "endereco": {"cidade": "Sessionville", "estado": "SS"}}],
            "familiares": []
        },
        "user_id": None,
        "access_token": None,
        "session_id": None,
        "dataset_id": None
    }

@pytest.mark.asyncio
async def test_session_flow(async_client: AsyncClient, test_data: dict):
    """
    Tests the complete session flow: DB setup, register, login, create, get, and finish.
    """
    # 1. --- Setup Database ---
    async for session in get_async_session():
        try:
            new_dataset = Dataset(name="Test Dataset for Sessions")
            session.add(new_dataset)
            await session.commit()
            test_data["dataset_id"] = new_dataset.id
        finally:
            await session.close()
    
    assert test_data["dataset_id"] is not None

    # 2. --- Register and Login ---
    reg_response = await async_client.post("/auth/register", json=test_data["user_data"])
    assert reg_response.status_code == 201
    test_data["user_id"] = reg_response.json()["id"]

    login_data = {
        "username": test_data["user_data"]["email"],
        "password": test_data["user_data"]["password"],
    }
    log_response = await async_client.post("/auth/jwt/login", data=login_data)
    assert log_response.status_code == 200
    access_token = log_response.json()["access_token"]
    
    async_client.headers["Authorization"] = f"Bearer {access_token}"

    # 3. --- Create Session ---
    session_data = {
        "dataset_id": test_data["dataset_id"],
        "notes": "Test session notes",
        "vocal_health_note": "Good",
        "termos": True
    }
    create_response = await async_client.post("/api/v1/sessions", json=session_data)
    assert create_response.status_code == 201
    session_id = create_response.json()["id"]

    # 4. --- Get Active Session ---
    get_response = await async_client.get(f"/api/v1/sessions/active-{test_data['user_id']}")
    assert get_response.status_code == 200
    response_data = get_response.json()
    assert len(response_data) == 1
    assert response_data[0]["id"] == session_id
    assert response_data[0]["status"] == "active"

    # 5. --- Finish Session ---
    finish_data = {"notes": "Session finished."}
    finish_response = await async_client.patch(f"/api/v1/sessions/{session_id}/finish", json=finish_data)
    assert finish_response.status_code == 200
    assert finish_response.json()["finished_at"] is not None
