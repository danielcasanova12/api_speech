import uuid
from datetime import datetime, date, timezone
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from fastapi_users import schemas

# --- Schemas para Entidades Relacionadas ---

class EnderecoSchema(BaseModel):
    cidade: str
    estado: str = Field(max_length=2)
    model_config = ConfigDict(from_attributes=True)

class HistoricoMoradiaCreate(BaseModel):
    periodo: str # "0-12 anos" ou "12-18 anos"
    endereco: EnderecoSchema

class HistoricoMoradiaRead(BaseModel):
    periodo: str
    endereco: EnderecoSchema
    model_config = ConfigDict(from_attributes=True)

class FamiliarCreate(BaseModel):
    nome: str
    grau_parentesco: str
    endereco: EnderecoSchema

class FamiliarRead(BaseModel):
    nome: str
    grau_parentesco: str
    endereco: EnderecoSchema
    model_config = ConfigDict(from_attributes=True)

class UserCreate(schemas.BaseUserCreate):
    nome_completo: str
    data_nascimento: date
    genero: str | None
    language: str

    cidade_nascimento: EnderecoSchema
    cidade_atual: EnderecoSchema

    historico_moradia: List[HistoricoMoradiaCreate]
    familiares: List[FamiliarCreate]

class UserUpdate(schemas.BaseUserUpdate):
    nome_completo: Optional[str] = None
    data_nascimento: Optional[date] = None
    genero: Optional[str] = None
    language: Optional[str] = None
    cidade_atual: Optional[EnderecoSchema] = None

class UserRead(schemas.BaseUser[uuid.UUID]):
    id: uuid.UUID
    nome_completo: str
    data_nascimento: date
    genero: str
    language: str
    is_active: bool

    cidade_nascimento: EnderecoSchema
    cidade_atual: EnderecoSchema
    historico_moradia: List[HistoricoMoradiaRead]
    familiares: List[FamiliarRead]

    model_config = ConfigDict(from_attributes=True)

# --- Auth Schemas ---

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: UserRead

class ForgotPasswordSchema(BaseModel):
    email: EmailStr

class ResetPasswordSchema(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)

# --- Session Schemas ---

class SessionCreate(BaseModel):
    dataset_id: int # Changed from UUID to int to match model
    notes: Optional[str] = None
    vocal_health_note: Optional[str] = None
    termos: bool

class SessionRead(BaseModel):
    id: int
    user_id: uuid.UUID
    dataset_id: int
    started_at: datetime
    finished_at: Optional[datetime] = None
    notes: Optional[str] = None
    vocal_health_note: Optional[str] = None
    termos: bool
    status: Optional[str] = None
    numero_frase: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class SessionUpdate(BaseModel):
    notes: Optional[str] = None
    finished_at: Optional[datetime] = None
    numero_frase: Optional[int] = None
    status: Optional[str] = None

class SessionList(SessionRead):
    recordings_count: int
    status: str

# --- Recording Schemas ---

class RecordingRead(BaseModel):

    id_recordings: int

    session_id: int

    dataset_id: int

    bloco_id: int
    frase_id: Optional[int] = None


    path_local: Optional[str] = None

    audio_url_drive: Optional[str] = None

    audio_url_s3: Optional[str] = None
    is_test: bool

    duration: float

    format: str

    sample_rate: int

    frase_content: Optional[str] = None

    room_tone_start: Optional[bool] = None

    room_tone_end: Optional[bool] = None

    created_at: datetime



    model_config = ConfigDict(from_attributes=True)


class RecordingCreate(BaseModel):
    session_id: int
    dataset_id: int
    bloco_id: int
    frase_id: Optional[int] = None
    duration: float
    format: str
    sample_rate: int
    frase_content: Optional[str] = None
    room_tone_start: Optional[float] = None
    room_tone_end: Optional[float] = None
    is_test: Optional[bool] = False


# --- Dataset Schemas ---



class DatasetBase(BaseModel):
    name: str



class DatasetCreate(DatasetBase):

    pass



class DatasetUpdate(DatasetBase):

    pass



class Dataset(DatasetBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- Frase Schemas ---

class FraseBase(BaseModel):
    texto: str
    bloco_id: int

class FraseCreate(FraseBase):
    pass

class FraseUpdate(FraseBase):
    pass

class FraseRead(FraseBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- Bloco Schemas ---

class BlocoBase(BaseModel):
    nome_bloco: str
    descricao: Optional[str] = None
    tipo: Optional[str] = None
    emocao_numerico: Optional[int] = None
    descricao_emocao: Optional[str] = None
    espontaniedade: Optional[int] = None



class BlocoCreate(BlocoBase):

    pass



class BlocoUpdate(BlocoBase):

    pass



class BlocoRead(BlocoBase):

    id: int

    model_config = ConfigDict(from_attributes=True)


