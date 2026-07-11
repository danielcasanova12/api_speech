
import os

import pytest

if os.getenv("RUN_INTEGRATION_TESTS") != "1":
    pytest.skip(
        "Legacy integration tests are opt-in; set RUN_INTEGRATION_TESTS=1.",
        allow_module_level=True,
    )

from httpx import AsyncClient
from fastapi import status
import uuid
import io

# Marcador para todos os testes neste arquivo
pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

async def test_register_user(client: AsyncClient):
    """
    Testa o registro de um novo usuário.
    """
    unique_email = f"testuser_{uuid.uuid4()}@example.com"
    user_data = {
        "email": unique_email,
        "password": "testpassword123",
        "nome_completo": "Test User",
        "data_nascimento": "1990-01-01",
        "genero": "Outro",
        "language": "pt-BR",
        "cidade_nascimento_id": 1, 
        "cidade_atual_id": 1
    }
    
    response = await client.post("/auth/register", json=user_data)
    
    # Non-standard 201 Created for this endpoint
    assert response.status_code == status.HTTP_201_CREATED 
    
    response_data = response.json()
    assert response_data["email"] == user_data["email"]
    assert "id" in response_data
    assert not response_data["is_active"]
    assert not response_data["is_superuser"]
    assert not response_data["is_verified"]

async def test_login_for_access_token(client: AsyncClient):
    """
    Testa o login do usuário e a obtenção de um token de acesso.
    """
    # Primeiro, registra um usuário para garantir que ele exista
    unique_email = f"testuser_{uuid.uuid4()}@example.com"
    password = "testpassword123"
    user_data = {
        "email": unique_email,
        "password": password,
        "nome_completo": "Login Test User",
        "data_nascimento": "1995-05-05",
        "genero": "Masculino",
        "language": "en-US",
        "cidade_nascimento_id": 1,
        "cidade_atual_id": 1
    }
    await client.post("/auth/register", json=user_data)

    # Tenta fazer login
    login_data = {
        "username": unique_email,
        "password": password
    }
    response = await client.post("/auth/jwt/login", data=login_data)
    
    assert response.status_code == status.HTTP_200_OK
    
    response_data = response.json()
    assert "access_token" in response_data
    assert response_data["token_type"] == "bearer"
    

# Helper function to get a valid token
async def get_auth_token(client: AsyncClient) -> str:
    unique_email = f"testuser_{uuid.uuid4()}@example.com"
    password = "testpassword123"
    user_data = {
        "email": unique_email,
        "password": password,
        "nome_completo": "Token User",
        "data_nascimento": "1992-02-02",
        "genero": "Feminino",
        "language": "fr-FR",
        "cidade_nascimento_id": 1,
        "cidade_atual_id": 1
    }
    await client.post("/auth/register", json=user_data)
    
    login_data = {"username": unique_email, "password": password}
    response = await client.post("/auth/jwt/login", data=login_data)
    return response.json()["access_token"]

# --- Testes para Datasets ---
async def test_create_and_get_datasets(client: AsyncClient):
    token = await get_auth_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    
    # Criar
    dataset_name = f"Test Dataset {uuid.uuid4()}"
    response_create = await client.post(
        "/api/v1/datasets", 
        json={"name": dataset_name}, 
        headers=headers
    )
    assert response_create.status_code == status.HTTP_201_CREATED
    created_dataset = response_create.json()
    assert created_dataset["name"] == dataset_name
    assert "id" in created_dataset

    # Obter todos
    response_get = await client.get("/api/v1/datasets", headers=headers)
    assert response_get.status_code == status.HTTP_200_OK
    datasets = response_get.json()
    assert isinstance(datasets, list)
    assert any(d["name"] == dataset_name for d in datasets)

# --- Testes para Blocos ---
async def test_create_and_get_blocos(client: AsyncClient):
    token = await get_auth_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    
    # Criar
    bloco_name = f"Test Bloco {uuid.uuid4()}"
    bloco_data = {
        "nome_bloco": bloco_name,
        "descricao": "Bloco de teste",
        "tipo": "Leitura",
        "emocao_numerico": 5,
        "descricao_emocao": "Neutro",
        "espontaniedade": 0
    }
    response_create = await client.post("/api/v1/blocos", json=bloco_data, headers=headers)
    assert response_create.status_code == status.HTTP_201_CREATED
    created_bloco = response_create.json()
    assert created_bloco["nome_bloco"] == bloco_name

    # Obter todos
    response_get = await client.get("/api/v1/blocos", headers=headers)
    assert response_get.status_code == status.HTTP_200_OK
    blocos = response_get.json()
    assert isinstance(blocos, list)
    assert any(b["nome_bloco"] == bloco_name for b in blocos)

# --- Testes para Frases ---
async def test_create_and_get_frases(client: AsyncClient):
    token = await get_auth_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Primeiro, criar um bloco para associar a frase
    bloco_name = f"Bloco para Frase {uuid.uuid4()}"
    bloco_data = {"nome_bloco": bloco_name, "descricao": "Teste"}
    bloco_response = await client.post("/api/v1/blocos", json=bloco_data, headers=headers)
    assert bloco_response.status_code == status.HTTP_201_CREATED
    bloco_id = bloco_response.json()["id"]

    # Criar frase
    frase_text = "Esta é uma frase de teste."
    frase_data = {"texto": frase_text, "bloco_id": bloco_id}
    response_create = await client.post("/api/v1/frases", json=frase_data, headers=headers)
    assert response_create.status_code == status.HTTP_201_CREATED
    created_frase = response_create.json()
    assert created_frase["texto"] == frase_text
    assert created_frase["bloco_id"] == bloco_id

    # Obter todas
    response_get = await client.get(f"/api/v1/frases/{bloco_id}", headers=headers)
    assert response_get.status_code == status.HTTP_200_OK
    frases = response_get.json()
    assert isinstance(frases, list)
    assert any(f["texto"] == frase_text for f in frases)

# --- Teste para Recordings ---
async def test_create_recording(client: AsyncClient):
    token = await get_auth_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Dependências: criar dataset, bloco, frase e sessão
    dataset_resp = await client.post("/api/v1/datasets", json={"name": f"Dataset Rec {uuid.uuid4()}"}, headers=headers)
    dataset_id = dataset_resp.json()["id"]

    bloco_resp = await client.post("/api/v1/blocos", json={"nome_bloco": f"Bloco Rec {uuid.uuid4()}"}, headers=headers)
    bloco_id = bloco_resp.json()["id"]

    frase_resp = await client.post("/api/v1/frases", json={"texto": "Frase para recording", "bloco_id": bloco_id}, headers=headers)
    frase_id = frase_resp.json()["id"]
    
    # Criar uma sessão para associar a gravação
    # NOTA: Assumindo que existe um endpoint para criar sessões. Se não, esta parte precisa de ajuste.
    # Por enquanto, vamos mockar o ID da sessão. Se existir um endpoint, usaremos ele.
    session_id = 1 # Mock ID, idealmente criar via endpoint

    # Criar um arquivo de áudio em memória
    audio_content = b"fake audio data"
    audio_file = io.BytesIO(audio_content)
    audio_file.name = "test.wav"

    # Dados do formulário
    form_data = {
        "frase_content": "Frase para recording",
        "dataset_id": str(dataset_id),
        "session_id": str(session_id),
        "is_test": "true",
        "bloco_id": str(bloco_id),
        "frase_id": str(frase_id),
        "duration": "1.23",
        "sample_rate": "44100",
        "format": "wav",
        "room_tone_start": "0.1",
        "room_tone_end": "0.5"
    }
    
    files = {"audio_file": (audio_file.name, audio_file, "audio/wav")}

    response = await client.post(
        "/api/v1/recordings",
        data=form_data,
        files=files,
        headers=headers
    )

    assert response.status_code == status.HTTP_201_CREATED
    recording_data = response.json()
    assert recording_data["frase_content"] == "Frase para recording"
    assert recording_data["dataset_id"] == dataset_id
    assert recording_data["session_id"] == session_id
    assert recording_data["is_test"] is True
    assert "audio_url_drive" in recording_data # Verifica se o upload (mock) funcionou
