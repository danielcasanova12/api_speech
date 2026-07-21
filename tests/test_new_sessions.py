
import os

import pytest

if os.getenv("RUN_INTEGRATION_TESTS") != "1":
    pytest.skip(
        "External session tests are opt-in; set RUN_INTEGRATION_TESTS=1.",
        allow_module_level=True,
    )

import httpx
from datetime import date
import uuid

pytestmark = pytest.mark.integration

DATASET_ID_1 = None
DATASET_ID_2 = None

BASE_URL = "http://127.0.0.1:8000/api/v1"
TEST_USER_EMAIL = f"integration_sessions_{uuid.uuid4()}@example.com"
TEST_USER_PASSWORD = "IntegrationTestPass123!"

async def get_auth_token(client):
    """Helper function to register (if needed) and log in a user."""
    global DATASET_ID_1, DATASET_ID_2
    # Create a separate client for authentication that targets the root URL
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as auth_client:
        # Ensure user exists (skipped for brevity, assuming existing user for now)
        register_payload = {
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD,
            "nome_completo": f"Test User {uuid.uuid4()}",
            "data_nascimento": str(date(1990, 1, 1)),
            "genero": "Outro",
            "language": "pt-BR",
            "cidade_nascimento": {"cidade": "Teste", "estado": "TS"},
            "cidade_atual": {"cidade": "Teste", "estado": "TS"},
            "historico_moradia": [{"periodo": "0-12 anos", "endereco": {"cidade": "Teste", "estado": "TS"}}],
            "familiares": [{"nome": "Familiar Teste", "grau_parentesco": "Pai/Mãe", "endereco": {"cidade": "Teste", "estado": "TS"}}]
        }
        await auth_client.post("/auth/register", json=register_payload)

        # Log in
        login_data = {"username": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
        login_response = await auth_client.post(
            "/auth/jwt/login",
            data=login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert login_response.status_code == 200, "Login failed"
        access_token = login_response.json()["access_token"]

    # Use the client with the /api/v1 prefix to create and retrieve datasets
    async with httpx.AsyncClient(base_url="http://localhost:8000/api/v1", headers={"Authorization": f"Bearer {access_token}"}) as api_client:
        # Ensure Dataset 1 exists
        try:
            create_response = await api_client.post("/datasets/", json={"name": "Test Dataset 1"})
            if create_response.status_code == 201:
                DATASET_ID_1 = create_response.json()["id"]
                print("Created Test Dataset 1")
            elif create_response.status_code == 400 and "already exists" in create_response.text:
                print("Test Dataset 1 already exists.")
        except httpx.HTTPStatusError as e:
            if not (e.response.status_code == 400 and "already exists" in e.response.text):
                raise

        # Ensure Dataset 2 exists
        try:
            create_response = await api_client.post("/datasets/", json={"name": "Test Dataset 2"})
            if create_response.status_code == 201:
                DATASET_ID_2 = create_response.json()["id"]
                print("Created Test Dataset 2")
            elif create_response.status_code == 400 and "already exists" in create_response.text:
                print("Test Dataset 2 already exists.")
        except httpx.HTTPStatusError as e:
            if not (e.response.status_code == 400 and "already exists" in e.response.text):
                raise

        # Retrieve all datasets to get the IDs if they already existed
        datasets_response = await api_client.get("/datasets/")
        datasets_response.raise_for_status() # Raise an exception for HTTP errors
        all_datasets = datasets_response.json()

        for ds in all_datasets:
            if ds["name"] == "Test Dataset 1":
                DATASET_ID_1 = ds["id"]
            elif ds["name"] == "Test Dataset 2":
                DATASET_ID_2 = ds["id"]

        assert DATASET_ID_1 is not None, "Failed to get ID for Test Dataset 1"
        assert DATASET_ID_2 is not None, "Failed to get ID for Test Dataset 2"

    return access_token

@pytest.mark.asyncio
async def test_session_creation_and_conflict():
    """
    Tests creating a session and getting a conflict on the second attempt.
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20) as client:
        access_token = await get_auth_token(client)
        auth_headers = {"Authorization": f"Bearer {access_token}"}

        session_payload = {
            "dataset_id": DATASET_ID_1, # Use a predictable dataset
            "notes": "Test de conflito",
            "vocal_health_note": "Normal",
            "termos": True,
        }

        # 1. First attempt: Create the session
        print("\\n--- Attempting to create a new session... ---")
        response_create = await client.post("/sessions", json=session_payload, headers=auth_headers)
        assert response_create.status_code == 201, f"Expected 201 CREATED, got {response_create.status_code}. Response: {response_create.text}"
        created_session = response_create.json()
        print("Session created successfully.")

        # 2. Second attempt: Should get a conflict
        print("\\n--- Attempting to create the same session again... ---")
        response_conflict = await client.post("/sessions", json=session_payload, headers=auth_headers)
        assert response_conflict.status_code == 409, f"Expected 409 CONFLICT, got {response_conflict.status_code}. Response: {response_conflict.text}"
        
        conflict_data = response_conflict.json()
        assert "detail" in conflict_data
        assert "session" in conflict_data["detail"]
        assert conflict_data["detail"]["session"]["id"] == created_session["id"]
        print("Successfully received 409 Conflict with existing session data.")

@pytest.mark.asyncio
async def test_update_session():
    """
    Tests updating an existing session with new data.
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20) as client:
        access_token = await get_auth_token(client)
        auth_headers = {"Authorization": f"Bearer {access_token}"}

        # 1. Ensure a session exists (or create one)
        session_payload = {
            "dataset_id": DATASET_ID_2, # Use a different dataset to avoid conflicts with other tests
            "notes": "Sessão para atualização",
            "vocal_health_note": "Boa",
            "termos": True,
        }
        response_create = await client.post("/sessions", json=session_payload, headers=auth_headers)
        
        # If it already exists, that's fine for this test.
        if response_create.status_code == 201:
            session_id = response_create.json()["id"]
            print(f"\\n--- Created new session with ID: {session_id} ---")
        elif response_create.status_code == 409:
            session_id = response_create.json()["detail"]["session"]["id"]
            print(f"\\n--- Using existing session with ID: {session_id} ---")
        else:
            pytest.fail(f"Failed to create or find a session for updating. Status: {response_create.status_code}, Response: {response_create.text}")

        # 2. Update the session
        update_payload = {
            "notes": "Nota atualizada",
            "numero_frase": 10
        }
        print(f"--- Updating session {session_id}... ---")
        response_update = await client.put(f"/sessions/{session_id}", json=update_payload, headers=auth_headers)

        assert response_update.status_code == 200, f"Expected 200 OK, got {response_update.status_code}. Response: {response_update.text}"
        
        updated_session = response_update.json()
        assert updated_session["notes"] == "Nota atualizada"
        assert updated_session["numero_frase"] == 10
        print("Session updated successfully.")
        print(f"Updated data: {updated_session}")

