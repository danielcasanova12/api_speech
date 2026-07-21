
import os

import pytest

if os.getenv("RUN_INTEGRATION_TESTS") != "1":
    pytest.skip(
        "Database E2E tests are opt-in; set RUN_INTEGRATION_TESTS=1.",
        allow_module_level=True,
    )

import uuid
import io
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from datetime import timedelta, timezone
import datetime

from main import app
from database import get_async_session
from models import User, HistoricoMoradia, Familiar, Dataset, Session, Recording

pytestmark = pytest.mark.integration

# Use a base URL that the test client will recognize
BASE_URL = "http://test"

@pytest.fixture(scope="module")
def test_data():
    return {
        "auth_user_data": {
            "email": f"testuser_auth_{uuid.uuid4()}@example.com",
            "password": "AuthPass123",
            "nome_completo": "Auth User",
            "data_nascimento": "1980-01-01",
            "genero": "male",
            "language": "en-US",
            "cidade_nascimento": {"cidade": "AuthCity", "estado": "AT"},
            "cidade_atual": {"cidade": "AuthTown", "estado": "AT"},
            "historico_moradia": [{"periodo": "0-12 anos", "endereco": {"cidade": "AuthCity", "estado": "AT"}}],
            "familiares": [{"nome": "AuthRelative", "grau_parentesco": "parent", "endereco": {"cidade": "AuthTown", "estado": "AT"}}]
        },
        "session_user_data": {
            "email": f"testuser_session_{uuid.uuid4()}@example.com",
            "password": "SessionPass123",
            "nome_completo": "Session User",
            "data_nascimento": "1990-01-01",
            "genero": "female",
            "language": "pt-BR",
            "cidade_nascimento": {"cidade": "SessionCity", "estado": "SS"},
            "cidade_atual": {"cidade": "SessionTown", "estado": "SS"},
            "historico_moradia": [{"periodo": "13-18 anos", "endereco": {"cidade": "SessionCity", "estado": "SS"}}],
            "familiares": []
        },
        "recording_user_data": {
            "email": f"testuser_recording_{uuid.uuid4()}@example.com",
            "password": "RecPass123",
            "nome_completo": "Recording User",
            "data_nascimento": "2000-01-01",
            "genero": "other",
            "language": "es-ES",
            "cidade_nascimento": {"cidade": "RecCity", "estado": "RC"},
            "cidade_atual": {"cidade": "RecTown", "estado": "RC"},
            "historico_moradia": [],
            "familiares": []
        },
        "auth_user_id": None,
        "auth_access_token": None,
        "session_user_id": None,
        "session_access_token": None,
        "recording_user_id": None,
        "recording_access_token": None,
        "test_dataset_id": None,
        "test_session_id": None,
    }

@pytest.mark.asyncio
async def test_full_e2e_flow(test_data: dict):
    """
    Tests the complete end-to-end flow of the API in a single async function.
    Includes database setup, user registration/login, session management, and recording creation.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        # --- Setup: Ensure a test dataset exists ---
        async for session in get_async_session():
            try:
                dataset_name = f"E2E Test Dataset_{uuid.uuid4()}"
                result = await session.execute(select(Dataset).where(Dataset.name == dataset_name))
                dataset = result.scalars().first()
                if not dataset:
                    new_dataset = Dataset(name=dataset_name)
                    session.add(new_dataset)
                    await session.commit()
                    await session.refresh(new_dataset)
                    test_data["test_dataset_id"] = new_dataset.id
                else:
                    test_data["test_dataset_id"] = dataset.id
            finally:
                await session.close()
        assert test_data["test_dataset_id"] is not None

        # --- 1. Authentication Flow ---
        # Register Auth User
        reg_response = await client.post("/auth/register", json=test_data["auth_user_data"])
        assert reg_response.status_code == 201, f"Auth registration failed: {reg_response.text}"
        test_data["auth_user_id"] = reg_response.json()["id"]
        
        # Login Auth User
        login_data = {"username": test_data["auth_user_data"]["email"], "password": test_data["auth_user_data"]["password"]}
        log_response = await client.post("/auth/jwt/login", data=login_data)
        assert log_response.status_code == 200, f"Auth login failed: {log_response.text}"
        test_data["auth_access_token"] = log_response.json()["access_token"]
        assert test_data["auth_access_token"] is not None

        # Verify Auth User in DB (optional, but good for E2E)
        async for db_session in get_async_session():
            try:
                user_result = await db_session.execute(
                    select(User).options(
                        selectinload(User.cidade_nascimento),
                        selectinload(User.cidade_atual),
                        selectinload(User.historico_moradia).selectinload(HistoricoMoradia.endereco),
                        selectinload(User.familiares).selectinload(Familiar.endereco)
                    ).where(User.id == test_data["auth_user_id"])
                )
                auth_user_db = user_result.scalars().one_or_none()
            finally:
                await db_session.close()
        assert auth_user_db.email == test_data["auth_user_data"]["email"]

        # --- 2. Session Flow (using a separate user) ---
        # Register Session User
        reg_response = await client.post("/auth/register", json=test_data["session_user_data"])
        assert reg_response.status_code == 201, f"Session user registration failed: {reg_response.text}"
        test_data["session_user_id"] = reg_response.json()["id"]

        # Login Session User
        login_data = {"username": test_data["session_user_data"]["email"], "password": test_data["session_user_data"]["password"]}
        log_response = await client.post("/auth/jwt/login", data=login_data)
        assert log_response.status_code == 200, f"Session user login failed: {log_response.text}"
        test_data["session_access_token"] = log_response.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {test_data['session_access_token']}"

        # Create Session
        session_data = {"dataset_id": test_data["test_dataset_id"], "notes": "E2E Session", "vocal_health_note": "Good", "termos": True}
        create_session_response = await client.post("/api/v1/sessions", json=session_data)
        assert create_session_response.status_code == 201, f"Create session failed: {create_session_response.text}"
        test_data["test_session_id"] = create_session_response.json()["id"]

        # Get Active Session
        get_session_response = await client.get(f"/api/v1/sessions/active-{test_data['session_user_id']}")
        assert get_session_response.status_code == 200, f"Get session failed: {get_session_response.text}"
        session_response_data = get_session_response.json()
        assert len(session_response_data) == 1
        assert session_response_data[0]["id"] == test_data["test_session_id"]
        assert session_response_data[0]["status"] == "active"

        # Finish Session
        future_time = datetime.datetime.now(timezone.utc) + timedelta(seconds=5)
        finish_data = {"notes": "Session finished in E2E.", "finished_at": future_time.isoformat()}
        finish_session_response = await client.patch(f"/api/v1/sessions/{test_data['test_session_id']}/finish", json=finish_data)
        assert finish_session_response.status_code == 200, f"Finish session failed: {finish_session_response.text}"
        assert finish_session_response.json()["finished_at"] is not None

        # --- 3. Recording Flow (using a separate user and the created session) ---
        # Register Recording User
        reg_response = await client.post("/auth/register", json=test_data["recording_user_data"])
        assert reg_response.status_code == 201, f"Recording user registration failed: {reg_response.text}"
        test_data["recording_user_id"] = reg_response.json()["id"]

        # Login Recording User
        login_data = {"username": test_data["recording_user_data"]["email"], "password": test_data["recording_user_data"]["password"]}
        log_response = await client.post("/auth/jwt/login", data=login_data)
        assert log_response.status_code == 200, f"Recording user login failed: {log_response.text}"
        test_data["recording_access_token"] = log_response.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {test_data['recording_access_token']}"

        # Create a Session for the Recording User
        rec_session_data = {"dataset_id": test_data["test_dataset_id"], "notes": "Recording Session", "vocal_health_note": "Good", "termos": True}
        create_rec_session_response = await client.post("/api/v1/sessions", json=rec_session_data)
        assert create_rec_session_response.status_code == 201, f"Create recording session failed: {create_rec_session_response.text}"
        test_data["test_session_id"] = create_rec_session_response.json()["id"]

        # Create Recording
        dummy_audio_content = io.BytesIO(b"RIFF\x00\x00\x00\x00WAVEfmt " + b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00data\x00\x00\x00\x00") # Minimal WAV header
        form_data = {
            "session_id": str(test_data["test_session_id"]),
            "dataset_id": str(test_data["test_dataset_id"]),
            "duration": "2.5",
            "format": "wav",
            "sample_rate": "16000",
            "emocao": "neutral",
        }
        files = {"audio_file": ("test_audio.wav", dummy_audio_content, "audio/wav")}

        create_rec_response = await client.post("/api/v1/recordings", data=form_data, files=files)
        assert create_rec_response.status_code == 201, f"Create recording failed: {create_rec_response.text}"
        
        response_data = create_rec_response.json()
        assert response_data["session_id"] == test_data["test_session_id"]
        assert response_data["format"] == "wav"
        assert "uploads" in response_data["path_local"]
