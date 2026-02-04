
import pytest
import uuid
import io
from httpx import AsyncClient
from sqlalchemy.future import select

from database import get_async_session
from models import Dataset

@pytest.fixture(scope="module")
def test_data():
    unique_id = uuid.uuid4()
    return {
        "user_data": {
            "email": f"testuser_recordings_{unique_id}@example.com",
            "password": "aVeryStrongPassword123",
            "nome_completo": "Recording Test User",
            "data_nascimento": "2000-01-01",
            "genero": "male",
            "language": "en-GB",
            "cidade_nascimento": {"cidade": "Recville", "estado": "RC"},
            "cidade_atual": {"cidade": "Recburg", "estado": "RC"},
            "historico_moradia": [],
            "familiares": []
        },
        "user_id": None,
        "access_token": None,
        "session_id": None,
        "dataset_id": None
    }

@pytest.mark.asyncio
async def test_recording_flow(async_client: AsyncClient, test_data: dict):
    """
    Tests the complete recording flow: setup, auth, create session, and create recording.
    """
    # 1. --- Setup Database ---
    async for session in get_async_session():
        try:
            # Use a unique name to avoid conflicts with other test files
            dataset_name = "Test Dataset for Recordings"
            result = await session.execute(select(Dataset).where(Dataset.name == dataset_name))
            dataset_obj = result.scalars().first()
            if not dataset_obj:
                new_dataset = Dataset(name=dataset_name)
                session.add(new_dataset)
                await session.commit()
                test_data["dataset_id"] = new_dataset.id
            else:
                test_data["dataset_id"] = dataset_obj.id
        finally:
            await session.close()
    
    assert test_data["dataset_id"] is not None
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

    # 2. --- Create a Session to Record In ---
    session_data = {
        "dataset_id": test_data["dataset_id"],
        "notes": "Session for recording test",
        "vocal_health_note": "Ready to record",
        "termos": True
    }
    create_session_response = await async_client.post("/api/v1/sessions", json=session_data)
    assert create_session_response.status_code == 201
    test_data["session_id"] = create_session_response.json()["id"]

    # 3. --- Create a Recording ---
    dummy_audio_content = io.BytesIO(b"RIFF...WAVEfmt...") # Dummy WAV header
    form_data = {
        "session_id": str(test_data["session_id"]),
        "dataset_id": str(test_data["dataset_id"]),
        "duration": "2.5",
        "format": "wav",
        "sample_rate": "16000",
        "emocao": "neutral",
    }
    files = {"audio_file": ("test_audio.wav", dummy_audio_content, "audio/wav")}
    
    create_rec_response = await async_client.post("/api/v1/recordings", data=form_data, files=files)
    assert create_rec_response.status_code == 201
    
    response_data = create_rec_response.json()
    assert response_data["session_id"] == test_data["session_id"]
    assert response_data["format"] == "wav"
    assert "uploads" in response_data["path_local"]
