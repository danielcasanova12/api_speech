from pydantic import BaseModel, Field, Json
from typing import Optional
from datetime import datetime

class RecordingUploadResponse(BaseModel):
    status: str = "success"
    message: str = "Arquivo salvo com sucesso"
    fileId: str
    driveFileId: Optional[str] = None
    uploadedAt: datetime

class ErrorDetail(BaseModel):
    field: str
    message: str

class ValidationErrorResponse(BaseModel):
    status: str = "error"
    code: str = "VALIDATION_ERROR"
    message: str = "Dados inválidos"
    errors: list[ErrorDetail]

class StatusResponse(BaseModel):
    status: str
    recordingId: str
    uploadedAt: Optional[datetime] = None
    driveFileId: Optional[str] = None

class SessionCreateRequest(BaseModel):
    userId: str
    nomedataset: str

class SessionCreateResponse(BaseModel):
    status: str = "success"
    sessionId: str
    createdAt: datetime

class Recording(BaseModel):
    id: str
    nomedataset: str
    id_secao: int
    emocao: str

class DeleteResponse(BaseModel):
    status: str = "success"
    message: str = "Gravação deletada com sucesso"
    recordingId: str

class DeviceInfo(BaseModel):
    userAgent: str
    platform: str
    language: str

class SectionCreateRequest(BaseModel):
    gender: str
    dataset_type: str

class SectionCreateResponse(BaseModel):
    status: str = "success"
    message: str = "Seção criada com sucesso"
    section_id: int
