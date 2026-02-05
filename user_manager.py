
import uuid
from typing import Optional

from sqlalchemy.orm import selectinload
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi import Depends, Request
from fastapi_users import BaseUserManager, UUIDIDMixin
import uuid
from typing import Optional

from config import settings
from database import get_async_session
from models import User, HistoricoMoradia, Familiar
from emails import send_reset_password_email, send_verification_email

class CustomSQLAlchemyUserDatabase(SQLAlchemyUserDatabase):
    async def get_by_email(self, email: str) -> Optional[User]:
        statement = select(self.user_table).options(
            selectinload(User.cidade_nascimento),
            selectinload(User.cidade_atual),
            selectinload(User.historico_moradia).selectinload(HistoricoMoradia.endereco),
            selectinload(User.familiares).selectinload(Familiar.endereco)
        ).where(self.user_table.email == email)
        return await self._get_user(statement)

    async def get(self, id: uuid.UUID) -> Optional[User]:
        statement = select(self.user_table).options(
            selectinload(User.cidade_nascimento),
            selectinload(User.cidade_atual),
            selectinload(User.historico_moradia).selectinload(HistoricoMoradia.endereco),
            selectinload(User.familiares).selectinload(Familiar.endereco)
        ).where(self.user_table.id == id)
        return await self._get_user(statement)

class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.SECRET_KEY
    verification_token_secret = settings.SECRET_KEY

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        print(f"User {user.id} has registered.")

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        print(f"User {user.id} has forgotten their password. Reset token: {token}")
        await send_reset_password_email(user.email, token)

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        print(f"Verification requested for user {user.id}. Verification token: {token}")
        await send_verification_email(user.email, token)

async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield CustomSQLAlchemyUserDatabase(session, User)

async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)

