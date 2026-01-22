
import uuid
from datetime import date
from pydantic import BaseModel, EmailStr
from fastapi_users import schemas

# --- Schemas para Entidades Relacionadas ---

class EnderecoSchema(BaseModel):
    cidade: str
    estado: str

class HistoricoMoradiaCreate(BaseModel):
    periodo: str # "0-12 anos" ou "12-18 anos"
    endereco: EnderecoSchema

class FamiliarCreate(BaseModel):
    nome: str
    grau_parentesco: str
    endereco: EnderecoSchema

# --- Schemas do Usuário (Leitura) ---

class HistoricoMoradiaRead(BaseModel):
    id: int
    periodo: str
    endereco: EnderecoSchema

    class Config:
        orm_mode = True

class FamiliarRead(BaseModel):
    id: int
    nome: str
    grau_parentesco: str
    endereco: EnderecoSchema

    class Config:
        orm_mode = True

class UserRead(schemas.BaseUser[uuid.UUID]):
    nome_completo: str
    data_nascimento: date
    genero: str | None
    cidade_nascimento: EnderecoSchema
    cidade_atual: EnderecoSchema
    historico_moradia: list[HistoricoMoradiaRead]
    familiares: list[FamiliarRead]

# --- Schemas do Usuário (Criação e Atualização) ---

class UserCreate(schemas.BaseUserCreate):
    nome_completo: str
    data_nascimento: date
    genero: str | None
    
    cidade_nascimento: EnderecoSchema
    cidade_atual: EnderecoSchema
    
    historico_moradia: list[HistoricoMoradiaCreate]
    familiares: list[FamiliarCreate]

class UserUpdate(schemas.BaseUserUpdate):
    nome_completo: str | None = None
    data_nascimento: date | None = None
    genero: str | None = None
    cidade_atual: EnderecoSchema | None = None

# --- Schemas para Sessions ---

class SessionCreate(BaseModel):
    dataset: str

class SessionRead(BaseModel):
    id: int
    dataset: str
    user_id: uuid.UUID
    created_at: datetime

    class Config:
        orm_mode = True
