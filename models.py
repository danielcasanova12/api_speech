

import uuid
from datetime import date, datetime, timezone
from typing import List

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import String, Date, ForeignKey, Integer, Float, Boolean, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Endereco(Base):
    __tablename__ = "enderecos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cidade: Mapped[str] = mapped_column(String(100), nullable=False)
    estado: Mapped[str] = mapped_column(String(2), nullable=False)  # Sigla do estado, ex: SP


class HistoricoMoradia(Base):
    __tablename__ = "historico_moradia"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    periodo: Mapped[str] = mapped_column(String(50), nullable=False)  # "0-12 anos" ou "12-18 anos"

    endereco_id: Mapped[int] = mapped_column(ForeignKey("enderecos.id"), nullable=False)
    endereco: Mapped["Endereco"] = relationship(lazy="joined")

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"), nullable=False)
    user: Mapped["User"] = relationship(back_populates="historico_moradia")


class Familiar(Base):
    __tablename__ = "familiares"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    grau_parentesco: Mapped[str] = mapped_column(String(50), nullable=False)

    endereco_id: Mapped[int] = mapped_column(ForeignKey("enderecos.id"), nullable=False)
    endereco: Mapped["Endereco"] = relationship(lazy="joined")

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"), nullable=False)
    user: Mapped["User"] = relationship(back_populates="familiares")


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "user"  # 'user' é o nome da tabela padrão do fastapi-users

    nome_completo: Mapped[str] = mapped_column(String(255), nullable=False)
    data_nascimento: Mapped[date] = mapped_column(Date, nullable=False)
    genero: Mapped[str] = mapped_column(String(50), nullable=True)
    language: Mapped[str] = mapped_column(String(50), nullable=True)

    # Relacionamento para endereço de nascimento
    cidade_nascimento_id: Mapped[int] = mapped_column(ForeignKey("enderecos.id"), nullable=False)
    cidade_nascimento: Mapped["Endereco"] = relationship(foreign_keys=[cidade_nascimento_id], lazy="joined")

    # Relacionamento para endereço atual
    cidade_atual_id: Mapped[int] = mapped_column(ForeignKey("enderecos.id"), nullable=False)
    cidade_atual: Mapped["Endereco"] = relationship(foreign_keys=[cidade_atual_id], lazy="joined")

    # Relacionamentos One-to-Many
    historico_moradia: Mapped[List["HistoricoMoradia"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    familiares: Mapped[List["Familiar"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    sessions: Mapped[List["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    password_resets: Mapped[List["PasswordReset"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class PasswordReset(Base):
    __tablename__ = "password_resets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    user: Mapped["User"] = relationship(back_populates="password_resets")


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    dataset_type: Mapped[str] = mapped_column(String(50), nullable=False, default="speech")
    sessions: Mapped[List["Session"]] = relationship(back_populates="dataset")
    recordings: Mapped[List["Recording"]] = relationship(back_populates="dataset")


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str] = mapped_column(String, nullable=True)
    vocal_health_note: Mapped[str] = mapped_column(String, nullable=True)
    termos: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(50), nullable=True, default="active")
    numero_frase: Mapped[int] = mapped_column(Integer, nullable=True)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    user: Mapped["User"] = relationship(back_populates="sessions")

    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"))
    dataset: Mapped["Dataset"] = relationship(back_populates="sessions")
    
    recordings: Mapped[List["Recording"]] = relationship(back_populates="session")


class Bloco(Base):
    __tablename__ = "blocos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome_bloco: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    descricao: Mapped[str] = mapped_column(String, nullable=True)
    tipo: Mapped[str] = mapped_column(String(50), nullable=True)
    emocao_numerico: Mapped[int] = mapped_column(Integer, nullable=True)
    descricao_emocao: Mapped[str] = mapped_column(String(255), nullable=True)
    espontaniedade: Mapped[int] = mapped_column(Integer, nullable=True) # 0 for No, 1 for Yes

    frases: Mapped[List["Frase"]] = relationship(back_populates="bloco", cascade="all, delete-orphan")
    recordings: Mapped[List["Recording"]] = relationship(back_populates="bloco")


class Frase(Base):
    __tablename__ = "frases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    texto: Mapped[str] = mapped_column(String, nullable=False)

    bloco_id: Mapped[int] = mapped_column(ForeignKey("blocos.id"))
    bloco: Mapped["Bloco"] = relationship(back_populates="frases")
    
    recordings: Mapped[List["Recording"]] = relationship(back_populates="frase")


class Recording(Base):
    __tablename__ = "recordings"
    id_recordings: Mapped[int] = mapped_column(Integer, primary_key=True)
    duration: Mapped[float] = mapped_column(Float, nullable=True)
    format: Mapped[str] = mapped_column(String(10), nullable=True)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=True)
    frase_content: Mapped[str] = mapped_column(String, nullable=True)
    room_tone_start: Mapped[float] = mapped_column(Float, nullable=True)
    room_tone_end: Mapped[float] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    path_local: Mapped[str] = mapped_column(String, nullable=True)
    audio_url_drive: Mapped[str] = mapped_column(String, nullable=True)
    audio_url_s3: Mapped[str] = mapped_column(String, nullable=True)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extra_info: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    session: Mapped["Session"] = relationship(back_populates="recordings")

    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"))
    dataset: Mapped["Dataset"] = relationship(back_populates="recordings")

    bloco_id: Mapped[int] = mapped_column(ForeignKey("blocos.id"))
    bloco: Mapped["Bloco"] = relationship(back_populates="recordings")

    frase_id: Mapped[int] = mapped_column(ForeignKey("frases.id"), nullable=True)
    frase: Mapped["Frase"] = relationship(back_populates="recordings")


class Music(Base):
    __tablename__ = "musics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    genero: Mapped[str] = mapped_column(String(100), nullable=False)
    texto: Mapped[str] = mapped_column(String, nullable=True)
    bpm: Mapped[int] = mapped_column(Integer, nullable=True)
    time_signature: Mapped[str] = mapped_column(String(50), nullable=True)
    vocal_audio_filepath: Mapped[str] = mapped_column(String, nullable=True)
    instrumental_audio_filepath: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
