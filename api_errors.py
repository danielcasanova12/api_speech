import logging
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApiError(Exception):
    code: str
    message: str
    status_code: int = status.HTTP_400_BAD_REQUEST
    details: Any | None = None
    field_errors: dict[str, list[str]] | None = None


class ResourceNotFoundError(ApiError):
    def __init__(self, code: str = "RESOURCE_NOT_FOUND", message: str = "O recurso informado não foi encontrado."):
        super().__init__(code=code, message=message, status_code=status.HTTP_404_NOT_FOUND)


class PermissionDeniedError(ApiError):
    def __init__(self, message: str = "Você não possui permissão para realizar esta operação."):
        super().__init__(
            code="PERMISSION_DENIED",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class AdminRequiredError(ApiError):
    def __init__(self):
        super().__init__(
            code="ADMIN_REQUIRED",
            message="Esta operação está disponível apenas para administradores.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ResourceConflictError(ApiError):
    def __init__(self, code: str = "RESOURCE_CONFLICT", message: str = "Não foi possível concluir a operação porque há um conflito com o estado atual."):
        super().__init__(code=code, message=message, status_code=status.HTTP_409_CONFLICT)


class StorageUnavailableError(ApiError):
    def __init__(self):
        super().__init__(
            code="STORAGE_UNAVAILABLE",
            message="Não foi possível acessar o arquivo solicitado no momento.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


ERROR_BY_STATUS: dict[int, tuple[str, str]] = {
    status.HTTP_400_BAD_REQUEST: (
        "BAD_REQUEST",
        "Não foi possível processar a solicitação. Verifique os dados enviados.",
    ),
    status.HTTP_401_UNAUTHORIZED: ("AUTHENTICATION_REQUIRED", "Faça login para continuar."),
    status.HTTP_403_FORBIDDEN: (
        "PERMISSION_DENIED",
        "Você não possui permissão para realizar esta operação.",
    ),
    status.HTTP_404_NOT_FOUND: ("RESOURCE_NOT_FOUND", "O recurso informado não foi encontrado."),
    status.HTTP_409_CONFLICT: (
        "RESOURCE_CONFLICT",
        "Não foi possível concluir a operação porque há um conflito com o estado atual.",
    ),
    status.HTTP_413_CONTENT_TOO_LARGE: (
        "FILE_TOO_LARGE",
        "O arquivo enviado ultrapassa o tamanho máximo permitido.",
    ),
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: (
        "UNSUPPORTED_AUDIO_FORMAT",
        "Envie um arquivo de áudio em um formato permitido.",
    ),
    status.HTTP_422_UNPROCESSABLE_CONTENT: (
        "VALIDATION_ERROR",
        "Verifique os campos informados.",
    ),
    status.HTTP_429_TOO_MANY_REQUESTS: (
        "TOO_MANY_REQUESTS",
        "Muitas solicitações foram feitas. Tente novamente em instantes.",
    ),
    status.HTTP_500_INTERNAL_SERVER_ERROR: (
        "INTERNAL_ERROR",
        "Não foi possível concluir a operação. Tente novamente em alguns instantes.",
    ),
    status.HTTP_503_SERVICE_UNAVAILABLE: (
        "STORAGE_UNAVAILABLE",
        "Não foi possível acessar o serviço solicitado no momento.",
    ),
}

DETAIL_CODE_OVERRIDES = {
    "Session not found": ("SESSION_NOT_FOUND", "A sessão informada não foi encontrada."),
    "Session not found.": ("SESSION_NOT_FOUND", "A sessão informada não foi encontrada."),
    "Recording not found.": ("RECORDING_NOT_FOUND", "A gravação informada não foi encontrada."),
    "Music not found": ("MUSIC_NOT_FOUND", "A música informada não foi encontrada."),
    "Audio file not found.": ("AUDIO_NOT_FOUND", "O arquivo de áudio não foi encontrado."),
    "Music audio file not found.": (
        "AUDIO_NOT_FOUND",
        "O arquivo de áudio da música não foi encontrado.",
    ),
    "Audio storage is temporarily unavailable.": (
        "STORAGE_UNAVAILABLE",
        "Não foi possível acessar o arquivo solicitado no momento.",
    ),
    "Cannot access recordings from another user.": (
        "PERMISSION_DENIED",
        "Você não possui permissão para acessar essas gravações.",
    ),
    "Cannot access recordings from another user's session.": (
        "PERMISSION_DENIED",
        "Você não possui permissão para acessar as gravações desta sessão.",
    ),
    "Este endereço de e-mail já está cadastrado.": (
        "RESOURCE_ALREADY_EXISTS",
        "Este endereço de e-mail já está cadastrado.",
    ),
}


def request_id_for(request: Request) -> str:
    header_value = request.headers.get("x-request-id")
    if header_value:
        return header_value
    existing = getattr(request.state, "request_id", None)
    if existing:
        return existing
    generated = str(uuid.uuid4())
    request.state.request_id = generated
    return generated


def error_payload(
    *,
    code: str,
    message: str,
    request_id: str,
    details: Any | None = None,
    field_errors: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "field_errors": field_errors,
            "request_id": request_id,
        },
    }


def json_error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request_id: str,
    details: Any | None = None,
    field_errors: dict[str, list[str]] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_payload(
            code=code,
            message=message,
            request_id=request_id,
            details=details,
            field_errors=field_errors,
        ),
        headers={"X-Request-ID": request_id},
    )


def _public_error_from_http(exc: StarletteHTTPException) -> tuple[str, str]:
    detail = exc.detail
    if isinstance(detail, dict):
        code = str(detail.get("code") or ERROR_BY_STATUS.get(exc.status_code, ERROR_BY_STATUS[500])[0])
        reason = detail.get("reason")
        if code == "REGISTER_INVALID_PASSWORD":
            return "VALIDATION_ERROR", str(reason or "Verifique a senha informada.")
        message = str(detail.get("message") or reason or ERROR_BY_STATUS.get(exc.status_code, ERROR_BY_STATUS[500])[1])
        return code, message

    if isinstance(detail, str):
        if detail in DETAIL_CODE_OVERRIDES:
            return DETAIL_CODE_OVERRIDES[detail]
        lowered = detail.lower()
        if "not authenticated" in lowered or "unauthorized" in lowered:
            return "AUTHENTICATION_REQUIRED", "Faça login para continuar."
        if "not a superuser" in lowered or "superuser" in lowered:
            return "ADMIN_REQUIRED", "Esta operação está disponível apenas para administradores."
        if "not found" in lowered:
            return ERROR_BY_STATUS[404]

    return ERROR_BY_STATUS.get(exc.status_code, ERROR_BY_STATUS[500])


def _field_name(loc: tuple[Any, ...]) -> str:
    public_parts = [str(part) for part in loc if part not in {"body", "query", "path", "header"}]
    return ".".join(public_parts) if public_parts else "request"


def _friendly_validation_message(error: dict[str, Any]) -> str:
    error_type = str(error.get("type", ""))
    context = error.get("ctx") or {}
    if error_type == "missing":
        return "Este campo é obrigatório."
    if "int_parsing" in error_type:
        return "Informe um número inteiro válido."
    if "float_parsing" in error_type:
        return "Informe um número válido."
    if "bool_parsing" in error_type:
        return "Informe verdadeiro ou falso."
    if "uuid_parsing" in error_type:
        return "O identificador informado é inválido."
    if "greater_than" in error_type:
        return f"O valor deve ser maior que {context.get('gt')}."
    if "greater_than_equal" in error_type:
        return f"O valor deve ser maior ou igual a {context.get('ge')}."
    if "less_than_equal" in error_type:
        return f"O valor deve ser menor ou igual a {context.get('le')}."
    if "string_too_short" in error_type:
        return "Informe um texto maior."
    if "string_too_long" in error_type:
        return "Informe um texto menor."
    if "literal_error" in error_type:
        return "Informe uma opção válida."
    if "value_error" in error_type:
        return "O valor informado não é válido."
    return "Verifique o valor informado."


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    request_id = request_id_for(request)
    logger.warning(
        "Domain error %s on %s %s request_id=%s",
        exc.code,
        request.method,
        request.url.path,
        request_id,
    )
    return json_error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
        field_errors=exc.field_errors,
        request_id=request_id,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = request_id_for(request)
    code, message = _public_error_from_http(exc)
    logger.info(
        "HTTP error %s on %s %s request_id=%s detail=%r",
        exc.status_code,
        request.method,
        request.url.path,
        request_id,
        exc.detail,
    )
    return json_error_response(
        status_code=exc.status_code,
        code=code,
        message=message,
        request_id=request_id,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    request_id = request_id_for(request)
    field_errors: dict[str, list[str]] = {}
    for error in exc.errors():
        field_errors.setdefault(_field_name(tuple(error.get("loc", ()))), []).append(
            _friendly_validation_message(error)
        )
    logger.info(
        "Validation error on %s %s request_id=%s errors=%s",
        request.method,
        request.url.path,
        request_id,
        exc.errors(),
    )
    return json_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="VALIDATION_ERROR",
        message="Verifique os campos informados.",
        field_errors=field_errors,
        request_id=request_id,
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    request_id = request_id_for(request)
    logger.exception(
        "Database error on %s %s request_id=%s",
        request.method,
        request.url.path,
        request_id,
    )
    return json_error_response(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="DATABASE_ERROR",
        message="Não foi possível acessar os dados no momento. Tente novamente em instantes.",
        request_id=request_id,
    )


async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = request_id_for(request)
    logger.exception(
        "Unexpected error on %s %s request_id=%s",
        request.method,
        request.url.path,
        request_id,
    )
    return json_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_ERROR",
        message="Não foi possível concluir a operação. Tente novamente em alguns instantes.",
        request_id=request_id,
    )


def install_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(Exception, unexpected_exception_handler)
