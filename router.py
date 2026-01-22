import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import (APIRouter, Depends, File, Form, Header, HTTPException,
                     UploadFile, status)

from auth_router import fastapi_users
from database import get_async_session
from models import Session, User
from schemas import SessionCreate, SessionRead

api_router = APIRouter()


@api_router.post(
    "/sessions",
    response_model=SessionRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Sessions"],
)
async def create_session(
    session_data: SessionCreate,
    user: User = Depends(fastapi_users.current_user(active=True)),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Cria uma nova sessão de gravação para o usuário autenticado.
    O gênero é obtido a partir do perfil do usuário.
    """
    new_session = Session(
        dataset=session_data.dataset,
        user_id=user.id,
        # O campo 'genero' não existe mais na tabela 'sessions',
        # mas pode ser acessado via user.genero se necessário em outra lógica.
    )
    session.add(new_session)
    await session.commit()
    await session.refresh(new_session)
    
    return new_session
