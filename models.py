from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# New Pydantic models for the API

class SessionCreate(BaseModel):
    genero: str
    dataset: str

class SessionResponse(BaseModel):
    id: int
    genero: str
    dataset: str

class RecordingCreate(BaseModel):
    id_session: int
    emocao: str

class RecordingResponse(BaseModel):
    id_audio: int
    id_session: int
    emocao: str
    file_path: str # To indicate where the audio is saved

# Existing/Modified response models (adjust as needed)
class RecordingUploadResponse(BaseModel):
    status: str = "success"
    message: str = "Arquivo salvo com sucesso"
    id_audio: int
    file_path: str
    uploadedAt: datetime

class ErrorDetail(BaseModel):
    field: str
    message: str

class ValidationErrorResponse(BaseModel):
    status: str = "error"
    code: str = "VALIDATION_ERROR"
    message: str = "Dados inválidos"
    errors: list[ErrorDetail]