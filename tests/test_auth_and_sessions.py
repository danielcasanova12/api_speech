
import os

import pytest

if os.getenv("RUN_INTEGRATION_TESTS") != "1":
    pytest.skip(
        "External API tests are opt-in; set RUN_INTEGRATION_TESTS=1.",
        allow_module_level=True,
    )

import httpx
import uuid
from datetime import date

pytestmark = pytest.mark.integration

# Use a base URL for the running application
BASE_URL = "http://localhost:8000"

# A fresh, non-personal account is registered for each test process.
TEST_USER_EMAIL = f"integration_auth_{uuid.uuid4()}@example.com"
TEST_USER_PASSWORD = "IntegrationTestPass123!"

@pytest.mark.asyncio
async def test_create_session_with_authentication():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # 1. Register the user to ensure they exist for the test
        # We don't care if this fails because the user already exists (400)
        
        # Generate a unique name for each test run to avoid conflicts
        unique_name = f"Test User {uuid.uuid4()}"
        
        register_payload = {
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD,
            "nome_completo": unique_name,
            "data_nascimento": str(date(1990, 1, 1)),
            "genero": "Outro",
            "language": "pt-BR",
            "cidade_nascimento": {"cidade": "Teste", "estado": "TS"},
            "cidade_atual": {"cidade": "Teste", "estado": "TS"},
            "historico_moradia": [
                {
                    "periodo": "0-12 anos",
                    "endereco": {"cidade": "Teste", "estado": "TS"}
                }
            ],
            "familiares": [
                {
                    "nome": "Familiar Teste",
                    "grau_parentesco": "Pai/Mãe",
                    "endereco": {"cidade": "Teste", "estado": "TS"}
                }
            ]
        }
        
        # We try to register, but if the user exists, it's fine.
        await client.post("/auth/register", json=register_payload)

        # 2. Log in to get the access token
        login_data = {
            "username": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        }
        login_response = await client.post(
            "/auth/jwt/login",
            data=login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        # Ensure login was successful
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        
        token_data = login_response.json()
        access_token = token_data.get("access_token")
        assert access_token, "Access token not found in login response"

        # 3. Use the token to create a session
        session_payload = {
            "dataset_id": 1,
            "notes": "Test session",
            "vocal_health_note": "Good",
            "termos": True
        }
        
        auth_headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        session_response = await client.post(
            "/api/v1/sessions",
            json=session_payload,
            headers=auth_headers
        )

        # 4. Assert that the session creation was successful
        assert session_response.status_code == 201, (
            f"Failed to create session. Expected 201, got {session_response.status_code}. "
            f"Response: {session_response.text}"
        )
        
        print("\n--- Test successful! ---")
        print(f"Session created successfully for user {TEST_USER_EMAIL}")
        print(f"Response: {session_response.json()}")
