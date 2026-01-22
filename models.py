
import uuid
from datetime import date
from typing import List

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import Column, String, Date, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

class Endereco(Base):
    __tablename__ = "enderecos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cidade: Mapped[str] = mapped_column(String(100), nullable=False)
    estado: Mapped[str] = mapped_column(String(2), nullable=False) # Sigla do estado, ex: SP

class HistoricoMoradia(Base):
    __tablename__ = "historico_moradia"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    periodo: Mapped[str] = mapped_column(String(50), nullable=False) # "0-12 anos" ou "12-18 anos"
    
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
    __tablename__ = "user" # 'user' é o nome da tabela padrão do fastapi-users
    
    nome_completo: Mapped[str] = mapped_column(String(255), nullable=False)
    data_nascimento: Mapped[date] = mapped_column(Date, nullable=False)
    genero: Mapped[str] = mapped_column(String(50), nullable=True)

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

class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    user: Mapped["User"] = relationship(back_populates="sessions")
