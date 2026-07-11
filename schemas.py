import uuid
from datetime import datetime, date
from typing import List, Literal, Optional
from pydantic import AwareDatetime, BaseModel, EmailStr, Field, ConfigDict
from fastapi_users import schemas

# --- Schemas para Entidades Relacionadas ---

class EnderecoSchema(BaseModel):
    cidade: str = Field(min_length=1, max_length=100)
    estado: str = Field(min_length=2, max_length=2)
    model_config = ConfigDict(from_attributes=True)

class HistoricoMoradiaCreate(BaseModel):
    periodo: str = Field(min_length=1, max_length=50)
    endereco: EnderecoSchema

class HistoricoMoradiaRead(BaseModel):
    periodo: str
    endereco: EnderecoSchema
    model_config = ConfigDict(from_attributes=True)

class FamiliarCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=255)
    grau_parentesco: str = Field(min_length=1, max_length=50)
    endereco: EnderecoSchema

class FamiliarRead(BaseModel):
    nome: str
    grau_parentesco: str
    endereco: EnderecoSchema
    model_config = ConfigDict(from_attributes=True)

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    nome_completo: str = Field(min_length=1, max_length=255)
    data_nascimento: date
    genero: str | None
    language: str = Field(min_length=1, max_length=50)

    cidade_nascimento: EnderecoSchema
    cidade_atual: EnderecoSchema

    historico_moradia: List[HistoricoMoradiaCreate]
    familiares: List[FamiliarCreate]

class UserUpdate(BaseModel):
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    email: Optional[EmailStr] = None
    nome_completo: Optional[str] = None
    data_nascimento: Optional[date] = None
    genero: Optional[str] = None
    language: Optional[str] = None
    cidade_atual: Optional[EnderecoSchema] = None

class UserRead(schemas.BaseUser[uuid.UUID]):
    id: uuid.UUID
    nome_completo: str
    data_nascimento: date
    genero: Optional[str] = None
    language: Optional[str] = None
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
    new_password: str = Field(..., min_length=8, max_length=128)

# --- Session Schemas ---

class SessionCreate(BaseModel):
    dataset_id: int = Field(gt=0)
    notes: Optional[str] = None
    vocal_health_note: Optional[str] = None
    termos: Literal[True]

class SessionRead(BaseModel):
    id: int
    user_id: uuid.UUID
    dataset_id: int
    started_at: datetime
    finished_at: Optional[datetime] = None
    notes: Optional[str] = None
    vocal_health_note: Optional[str] = None
    termos: bool
    status: Optional[Literal["active", "finished", "cancelled"]] = None
    numero_frase: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class SessionUpdate(BaseModel):
    notes: Optional[str] = None
    finished_at: Optional[AwareDatetime] = None
    numero_frase: Optional[int] = Field(default=None, ge=1)
    status: Optional[Literal["active", "finished", "cancelled"]] = None

class SessionList(SessionRead):
    recordings_count: int
    status: str


class RecentSessionsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[SessionList]

# --- Recording Schemas ---

class RecordingRead(BaseModel):

    id_recordings: int

    session_id: int

    dataset_id: int

    bloco_id: int
    frase_id: Optional[int] = None


    is_test: bool

    duration: Optional[float] = None

    format: Optional[str] = None

    sample_rate: Optional[int] = None

    frase_content: Optional[str] = None

    room_tone_start: Optional[float] = None

    room_tone_end: Optional[float] = None

    created_at: datetime

    extra_info: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)


class RecordingDetailRead(RecordingRead):
    session_started_at: Optional[datetime] = None
    session_status: Optional[str] = None
    user_id: uuid.UUID
    dataset_name: Optional[str] = None
    dataset_type: Optional[str] = None
    bloco_nome: Optional[str] = None
    bloco_tipo: Optional[str] = None
    frase_texto: Optional[str] = None


class RecordingAudioRead(BaseModel):
    id_recordings: int
    session_id: int
    dataset_id: int
    bloco_id: int
    frase_id: Optional[int] = None
    duration: Optional[float] = None
    format: Optional[str] = None
    sample_rate: Optional[int] = None
    frase_content: Optional[str] = None
    is_test: bool
    created_at: datetime
    audio_url: Optional[str] = None
    audio_source: Optional[Literal["s3", "local"]] = None
    audio_available: bool = False
    expires_in: Optional[int] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class RecordingAudioAccessResponse(BaseModel):
    recording_id: int
    audio_available: bool
    audio_url: Optional[str] = None
    expires_in: Optional[int] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    created_at: Optional[datetime] = None


class RecordingListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[RecordingAudioRead]


class SessionRecordingsResponse(RecordingListResponse):
    session_id: int
    user_id: uuid.UUID


class RecordingCreate(BaseModel):
    session_id: int = Field(gt=0)
    dataset_id: int = Field(gt=0)
    bloco_id: int = Field(gt=0)
    frase_id: Optional[int] = None
    duration: float = Field(gt=0)
    format: str = Field(min_length=1, max_length=10)
    sample_rate: int = Field(ge=8000, le=384000)
    frase_content: Optional[str] = None
    room_tone_start: Optional[float] = None
    room_tone_end: Optional[float] = None
    is_test: Optional[bool] = False
    extra_info: Optional[dict] = None


# --- Dataset Schemas ---



class DatasetBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    dataset_type: str = Field(default="speech", pattern="^(speech|music|singing)$")



class DatasetCreate(DatasetBase):

    pass



class DatasetUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    dataset_type: Optional[str] = Field(
        default=None,
        pattern="^(speech|music|singing)$",
    )



class Dataset(DatasetBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- Frase Schemas ---

class FraseBase(BaseModel):
    texto: str = Field(min_length=1)
    bloco_id: int = Field(gt=0)

class FraseCreate(FraseBase):
    pass

class FraseUpdate(FraseBase):
    pass

class FraseRead(FraseBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- Music Schemas ---

class MusicCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=255)
    genero: str = Field(min_length=1, max_length=100)
    texto: Optional[str] = None
    bpm: Optional[int] = Field(default=None, ge=1, le=400)
    time_signature: Optional[str] = None

class MusicUpdate(BaseModel):
    nome: Optional[str] = None
    genero: Optional[str] = None
    texto: Optional[str] = None
    bpm: Optional[int] = Field(default=None, ge=1, le=400)
    time_signature: Optional[str] = None

class MusicListResponse(BaseModel):
    id: int
    nome: str
    genero: str
    bpm: Optional[int] = None
    time_signature: Optional[str] = None
    has_vocal_audio: bool
    has_instrumental_audio: bool
    vocal_audio_url: Optional[str] = None
    instrumental_audio_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class MusicDetailResponse(BaseModel):
    id: int
    nome: str
    genero: str
    texto: Optional[str] = None
    bpm: Optional[int] = None
    time_signature: Optional[str] = None
    vocal_audio_url: Optional[str] = None
    instrumental_audio_url: Optional[str] = None
    has_vocal_audio: bool
    has_instrumental_audio: bool

    model_config = ConfigDict(from_attributes=True)


class MusicAudioAccessResponse(BaseModel):
    music_id: int
    kind: Literal["vocal", "instrumental"]
    audio_available: bool
    audio_url: Optional[str] = None
    expires_in: Optional[int] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None


# --- Bloco Schemas ---

class BlocoBase(BaseModel):
    nome_bloco: str = Field(min_length=1, max_length=255)
    descricao: Optional[str] = None
    tipo: Optional[str] = None
    emocao_numerico: Optional[int] = None
    descricao_emocao: Optional[str] = None
    espontaniedade: Optional[int] = Field(default=None, ge=0, le=1)



class BlocoCreate(BlocoBase):

    pass



class BlocoUpdate(BlocoBase):

    pass



class BlocoRead(BlocoBase):

    id: int

    model_config = ConfigDict(from_attributes=True)


