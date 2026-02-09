
import pytest
import httpx
import uuid
from datetime import date, datetime
import io

# URL base para a aplicação em execução
BASE_URL = "http://localhost:8000"

# Usaremos um email único para cada execução de teste para evitar conflitos
UNIQUE_EMAIL = f"testuser_{uuid.uuid4()}@example.com"
TEST_USER_PASSWORD = "a_secure_password_123"

# Armazenará o token de autenticação para uso nos testes
access_token = None

# ---- Fixtures e Funções de Ajuda ----

@pytest.fixture(scope="module")
async def register_and_login_user():
    """
    Fixture para registrar um novo usuário e fazer login para obter um token de acesso.
    Este token será reutilizado em todos os testes do módulo.
    """
    global access_token
    async with httpx.AsyncClient(base_url=BASE_URL, follow_redirects=True, timeout=30.0) as client:
        # 1. Registrar um usuário único
        register_payload = {
            "email": UNIQUE_EMAIL,
            "password": TEST_USER_PASSWORD,
            "nome_completo": f"Test User {uuid.uuid4()}",
            "data_nascimento": str(date(1995, 5, 15)),
            "genero": "Não-binário",
            "language": "pt-BR",
            "cidade_nascimento": {"cidade": "Cidade Teste", "estado": "TS"},
            "cidade_atual": {"cidade": "Cidade Atual", "estado": "TS"},
            "historico_moradia": [],
            "familiares": []
        }
        
        register_response = await client.post("/auth/register", json=register_payload)
        assert register_response.status_code == 201, f"Falha no registro: {register_response.text}"
        
        # 2. Fazer login para obter o token
        login_data = {"username": UNIQUE_EMAIL, "password": TEST_USER_PASSWORD}
        login_response = await client.post("/auth/jwt/login", data=login_data)
        
        assert login_response.status_code == 200, f"Falha no login: {login_response.text}"
        
        token_data = login_response.json()
        access_token = token_data.get("access_token")
        assert access_token is not None, "Token de acesso não encontrado na resposta de login."
        
        yield # Permite que os testes sejam executados
        
# ---- Testes E2E ----

@pytest.mark.asyncio
@pytest.mark.usefixtures("register_and_login_user")
class TestE2EFlow:
    
    created_ids = {}

    async def test_01_create_dataset(self):
        """Testa a criação de um novo dataset."""
        async with httpx.AsyncClient(base_url=BASE_URL, follow_redirects=True, timeout=30.0) as client:
            dataset_payload = {
                "name": f"Dataset de Teste {uuid.uuid4()}"
            }
            headers = {"Authorization": f"Bearer {access_token}"}
            
            response = await client.post("/api/v1/datasets", json=dataset_payload, headers=headers)
            
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["name"] == dataset_payload["name"]
            self.created_ids["dataset_id"] = response_data["id"]
            
    async def test_02_create_session(self):
        """Testa a criação de uma sessão vinculada ao dataset."""
        assert "dataset_id" in self.created_ids, "ID do dataset não foi criado."
        async with httpx.AsyncClient(base_url=BASE_URL, follow_redirects=True, timeout=30.0) as client:
            session_payload = {
                "dataset_id": self.created_ids["dataset_id"],
                "notes": "Sessão de teste E2E",
                "vocal_health_note": "Saudável",
                "termos": True
            }
            headers = {"Authorization": f"Bearer {access_token}"}
            
            response = await client.post("/api/v1/sessions", json=session_payload, headers=headers)
            
            assert response.status_code == 201
            response_data = response.json()
            assert response_data["dataset_id"] == self.created_ids["dataset_id"]
            self.created_ids["session_id"] = response_data["id"]

    async def test_03_create_bloco_and_frase(self):
        """Testa a criação de um bloco e uma frase."""
        async with httpx.AsyncClient(base_url=BASE_URL, follow_redirects=True, timeout=30.0) as client:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Criar Bloco
            bloco_payload = {"nome_bloco": f"Bloco de Teste E2E {uuid.uuid4()}", "descricao": "Teste"}
            bloco_response = await client.post("/api/v1/blocos", json=bloco_payload, headers=headers)
            assert bloco_response.status_code == 201
            self.created_ids["bloco_id"] = bloco_response.json()["id"]

            # Criar Frase
            frase_payload = {
                "texto": "Esta é uma frase de teste.",
                "bloco_id": self.created_ids["bloco_id"]
            }
            frase_response = await client.post("/api/v1/frases", json=frase_payload, headers=headers)
            assert frase_response.status_code == 201
            self.created_ids["frase_id"] = frase_response.json()["id"]

    async def test_04_upload_recording(self):
        """Testa o upload de uma gravação."""
        assert all(k in self.created_ids for k in ["session_id", "frase_id"]), "IDs de sessão ou frase não criados."
        async with httpx.AsyncClient(base_url=BASE_URL, follow_redirects=True, timeout=30.0) as client:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Simula um arquivo de áudio em memória
            audio_content = io.BytesIO(b"dummy audio data").read()
            files = {'audio_file': ('test.wav', audio_content, 'audio/wav')}
            
            data = {
                "session_id": str(self.created_ids["session_id"]),
                "dataset_id": "1",
                "bloco_id": str(self.created_ids["bloco_id"]),
                "frase_id": str(self.created_ids["frase_id"] if "frase_id" in self.created_ids else ""),
                "duration": str(10.5),
                "format": "wav",
                "sample_rate": str(44100),
            }
            response = await client.post("/api/v1/recordings", data=data, files=files, headers=headers)
            
            assert response.status_code == 201, f"Falha no upload da gravação: {response.text}"
            response_data = response.json()
            assert response_data["session_id"] == self.created_ids["session_id"]
            assert "file_path" in response_data

    async def test_05_list_endpoints(self):
        """Testa os endpoints de listagem (GET)."""
        async with httpx.AsyncClient(base_url=BASE_URL, follow_redirects=True, timeout=30.0) as client:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            endpoints = [
                "/api/v1/datasets",
                "/api/v1/blocos",
            ]
            
            for endpoint in endpoints:
                response = await client.get(endpoint, headers=headers)
                assert response.status_code == 200, f"Falha ao listar {endpoint}: {response.text}"
                assert isinstance(response.json(), list)

    async def test_06_get_user_me(self):
        """Testa o endpoint para obter o usuário atual."""
        async with httpx.AsyncClient(base_url=BASE_URL, follow_redirects=True, timeout=30.0) as client:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = await client.get("/users/me", headers=headers)
            
            assert response.status_code == 200
            user_data = response.json()
            assert user_data["email"] == UNIQUE_EMAIL
            assert "id" in user_data
