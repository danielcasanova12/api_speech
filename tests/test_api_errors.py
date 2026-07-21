from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api_errors import ResourceNotFoundError, install_exception_handlers
from main import app


def assert_standard_error(payload):
    assert payload["success"] is False
    assert set(payload["error"]) == {
        "code",
        "message",
        "details",
        "field_errors",
        "request_id",
    }
    assert payload["error"]["request_id"]


def test_unauthenticated_error_uses_standard_shape():
    response = TestClient(app).get("/api/v1/recordings")

    assert response.status_code == 401
    payload = response.json()
    assert_standard_error(payload)
    assert payload["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert payload["error"]["message"] == "Faça login para continuar."


def test_validation_error_has_field_errors():
    response = TestClient(app).get("/api/v1/datasets/not-an-int")

    assert response.status_code == 422
    payload = response.json()
    assert_standard_error(payload)
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert "dataset_id" in payload["error"]["field_errors"]
    assert payload["error"]["field_errors"]["dataset_id"] == [
        "Informe um número inteiro válido."
    ]


def test_not_found_error_uses_stable_code():
    local_app = FastAPI()
    install_exception_handlers(local_app)

    @local_app.get("/not-found")
    async def not_found():
        raise HTTPException(status_code=404, detail="Not Found")

    response = TestClient(local_app).get("/not-found")

    assert response.status_code == 404
    payload = response.json()
    assert_standard_error(payload)
    assert payload["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert payload["error"]["message"] == "O recurso informado não foi encontrado."


def test_domain_error_is_converted_to_standard_shape():
    local_app = FastAPI()
    install_exception_handlers(local_app)

    @local_app.get("/domain-error")
    async def domain_error():
        raise ResourceNotFoundError(
            code="RECORDING_NOT_FOUND",
            message="A gravação informada não foi encontrada.",
        )

    response = TestClient(local_app).get("/domain-error")

    assert response.status_code == 404
    payload = response.json()
    assert_standard_error(payload)
    assert payload["error"]["code"] == "RECORDING_NOT_FOUND"
    assert payload["error"]["message"] == "A gravação informada não foi encontrada."


def test_unexpected_error_does_not_expose_technical_detail():
    local_app = FastAPI()
    install_exception_handlers(local_app)

    @local_app.get("/unexpected-error")
    async def unexpected_error():
        raise RuntimeError("private stack trace detail")

    response = TestClient(local_app, raise_server_exceptions=False).get(
        "/unexpected-error"
    )

    assert response.status_code == 500
    payload = response.json()
    assert_standard_error(payload)
    assert payload["error"]["code"] == "INTERNAL_ERROR"
    assert "private stack trace detail" not in response.text
