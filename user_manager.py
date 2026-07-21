
import logging
import uuid
from typing import Any, Mapping, Optional

from sqlalchemy.orm import selectinload
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi import Depends, Request
from fastapi_users import BaseUserManager, UUIDIDMixin, exceptions

from config import settings
from database import get_async_session
from models import User, Endereco, HistoricoMoradia, Familiar
from emails import send_reset_password_email, send_verification_email


logger = logging.getLogger(__name__)
_MISSING = object()


def normalize_email(email: str) -> str:
    return str(email).strip().lower()


class CustomSQLAlchemyUserDatabase(SQLAlchemyUserDatabase):
    async def get_by_email(self, email: str) -> Optional[User]:
        statement = select(self.user_table).options(
            selectinload(User.cidade_nascimento),
            selectinload(User.cidade_atual),
            selectinload(User.historico_moradia).selectinload(HistoricoMoradia.endereco),
            selectinload(User.familiares).selectinload(Familiar.endereco)
        ).where(func.lower(self.user_table.email) == normalize_email(email))
        return await self._get_user(statement)

    async def get(self, id: uuid.UUID) -> Optional[User]:
        statement = select(self.user_table).options(
            selectinload(User.cidade_nascimento),
            selectinload(User.cidade_atual),
            selectinload(User.historico_moradia).selectinload(HistoricoMoradia.endereco),
            selectinload(User.familiares).selectinload(Familiar.endereco)
        ).where(self.user_table.id == id)
        return await self._get_user(statement)

    async def update(self, user: User, update_dict: dict[str, Any]) -> User:
        """Update scalar fields and the nested current address atomically."""
        values = dict(update_dict)
        address_update = values.pop("cidade_atual", _MISSING)

        if "email" in values and values["email"] is not None:
            values["email"] = normalize_email(values["email"])

        for key, value in values.items():
            setattr(user, key, value)

        # cidade_atual is non-nullable. Explicit null therefore means "no
        # change" instead of replacing the relationship with an invalid value.
        if address_update is not _MISSING and address_update is not None:
            if hasattr(address_update, "model_dump"):
                address_values = address_update.model_dump()
            elif isinstance(address_update, Mapping):
                address_values = dict(address_update)
            else:
                raise TypeError("cidade_atual must be an address object")

            if user.cidade_atual is None:
                user.cidade_atual = Endereco(**address_values)
            else:
                user.cidade_atual.cidade = address_values["cidade"]
                user.cidade_atual.estado = address_values["estado"]

        self.session.add(user)
        try:
            await self.session.commit()
            await self.session.refresh(user)
            return user
        except Exception:
            await self.session.rollback()
            raise

class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.SECRET_KEY
    verification_token_secret = settings.SECRET_KEY

    async def validate_password(self, password: str, user) -> None:
        if len(password) < 8:
            raise exceptions.InvalidPasswordException(
                reason="A senha deve ter pelo menos 8 caracteres."
            )
        if len(password) > 128:
            raise exceptions.InvalidPasswordException(
                reason="A senha deve ter no máximo 128 caracteres."
            )

    async def _update(self, user: User, update_dict: dict[str, Any]) -> User:
        normalized_update = dict(update_dict)
        if normalized_update.get("email") is not None:
            normalized_update["email"] = normalize_email(normalized_update["email"])
        return await super()._update(user, normalized_update)

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        logger.info("User %s registered", user.id)

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        logger.info("Password reset requested for user %s", user.id)
        await send_reset_password_email(user.email, token)

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        logger.info("Verification requested for user %s", user.id)
        await send_verification_email(user.email, token)

async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield CustomSQLAlchemyUserDatabase(session, User)

async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)
