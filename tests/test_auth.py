import pytest
import pytest_asyncio
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.orm import selectinload
from sqlalchemy.future import select

from main import app
from database import get_async_session
from models import User, HistoricoMoradia, Familiar

# Use a base URL that the test client will recognize
BASE_URL = "http://test"

@pytest.fixture(scope="module")
def test_data():
    unique_id = uuid.uuid4()
    return {
        "user_data": {
            "email": f"testuser_{unique_id}@example.com",
            "password": "aVeryStrongPassword123",
            "nome_completo": "Test User",
            "data_nascimento": "1990-01-01",
            "genero": "other",
            "language": "en-US",
            "cidade_nascimento": {"cidade": "Testville", "estado": "TS"},
            "cidade_atual": {"cidade": "Testburg", "estado": "TS"},
            "historico_moradia": [{"periodo": "0-12 anos", "endereco": {"cidade": "Testville", "estado": "TS"}}],
            "familiares": [{"nome": "Test Relative", "grau_parentesco": "parent", "endereco": {"cidade": "Testburg", "estado": "TS"}}]
        },
        "user_id": None,
        "access_token": None
    }

@pytest.mark.asyncio
async def test_auth_flow(async_client: AsyncClient, test_data: dict):
    """
    Tests the complete authentication flow: register, login, and DB verification.
    """
    # 1. --- Test User Registration ---
    response = await async_client.post("/auth/register", json=test_data["user_data"])
    assert response.status_code == 201, f"Registration failed: {response.text}"
    
    response_data = response.json()
    assert response_data["email"] == test_data["user_data"]["email"]
    assert "id" in response_data
    test_data["user_id"] = response_data["id"]

    # 2. --- Test User Login ---
    login_data = {
        "username": test_data["user_data"]["email"],
        "password": test_data["user_data"]["password"],
    }
    response = await async_client.post("/auth/jwt/login", data=login_data)
    assert response.status_code == 200, f"Login failed: {response.text}"
    
    response_data = response.json()
    assert "access_token" in response_data
    test_data["access_token"] = response_data["access_token"]

    # 3. --- Verify in Database ---
    async for session in get_async_session():
        try:
            result = await session.execute(
                select(User).options(
                    selectinload(User.cidade_nascimento),
                    selectinload(User.cidade_atual),
                    selectinload(User.historico_moradia).selectinload(HistoricoMoradia.endereco),
                    selectinload(User.familiares).selectinload(Familiar.endereco)
                ).where(User.id == test_data["user_id"])
            )
            user = result.scalars().one_or_none()
        finally:
            await session.close()
            
    assert user is not None
    assert user.email == test_data["user_data"]["email"]
    assert user.cidade_nascimento.cidade == "Testville"
    assert len(user.historico_moradia) == 1
    assert user.historico_moradia[0].endereco.cidade == "Testville"
    assert len(user.familiares) == 1
    assert user.familiares[0].nome == "Test Relative"