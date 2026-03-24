import os
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from database import get_async_session
from models import User, Recording, Session
from auth_router import fastapi_users
from schemas import RecordingRead

# Dependência para garantir que apenas superusuários acessem
current_superuser = fastapi_users.current_user(active=True, superuser=True)

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/recordings/{recording_id}/play", response_class=FileResponse)
async def play_recording(
    recording_id: int,
    user: User = Depends(current_superuser),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Retorna o arquivo de áudio físico para ser reproduzido diretamente no Swagger ou navegador.
    Apenas superusuários.
    """
    result = await db.execute(select(Recording).where(Recording.id_recordings == recording_id))
    recording = result.scalars().first()

    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gravação não encontrada."
        )
    
    if not recording.path_local or not os.path.exists(recording.path_local):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo de áudio físico não encontrado no servidor."
        )

    return FileResponse(path=recording.path_local)

@router.get("/users/ids", response_model=List[uuid.UUID])
async def get_all_user_ids(
    user: User = Depends(current_superuser),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Retorna uma lista com os IDs de todos os usuários cadastrados.
    Apenas superusuários.
    """
    result = await db.execute(select(User.id))
    ids = result.scalars().all()
    return ids

@router.get("/users/id-by-email", response_model=uuid.UUID)
async def get_user_id_by_email(
    email: str,
    user: User = Depends(current_superuser),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Busca o ID de um usuário através do seu e-mail.
    Apenas superusuários.
    """
    result = await db.execute(select(User.id).where(User.email == email))
    user_id = result.scalars().first()
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuário com email '{email}' não encontrado."
        )
    return user_id

@router.get("/users/{user_id}/recordings", response_model=List[RecordingRead])
async def get_user_recordings(
    user_id: uuid.UUID,
    user: User = Depends(current_superuser),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Recupera todas as gravações associadas a um ID de usuário específico.
    Apenas superusuários.
    """
    result = await db.execute(
        select(Recording)
        .join(Session)
        .where(Session.user_id == user_id)
    )
    recordings = result.scalars().all()
    return recordings

@router.get("/sessions/{session_id}/recordings", response_model=List[RecordingRead])
async def get_session_recordings(
    session_id: int,
    user: User = Depends(current_superuser),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Recupera todas as gravações associadas a uma sessão específica.
    Apenas superusuários.
    """
    result = await db.execute(
        select(Recording)
        .where(Recording.session_id == session_id)
    )
    recordings = result.scalars().all()
    return recordings

@router.delete("/users/delete-by-email", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_and_data_by_email(
    email: str,
    user: User = Depends(current_superuser), # Garante que quem chama é admin
    db: AsyncSession = Depends(get_async_session),
):
    """
    LGPD Compliance: Deleta permanentemente um usuário e TODOS os seus dados associados (sessões, gravações, arquivos).
    Apenas superusuários podem executar esta ação.
    """
    # 1. Buscar o usuário alvo
    result = await db.execute(select(User).where(User.email == email))
    target_user = result.scalars().first()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuário com email '{email}' não encontrado."
        )

    # Não permitir que o admin se delete a si mesmo por engano (opcional, mas seguro)
    if target_user.id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode deletar sua própria conta de administrador por aqui."
        )

    print(f"Iniciando deleção completa para o usuário: {target_user.email} (ID: {target_user.id})")

    # 2. Buscar e deletar arquivos físicos (Recordings)
    # Precisamos carregar as gravações antes de deletar o usuário
    recordings_result = await db.execute(
        select(Recording)
        .join(Session)
        .where(Session.user_id == target_user.id)
    )
    recordings = recordings_result.scalars().all()

    deleted_files_count = 0
    errors_count = 0

    for recording in recordings:
        if recording.path_local:
            try:
                if os.path.exists(recording.path_local):
                    os.remove(recording.path_local)
                    deleted_files_count += 1
                    print(f"Arquivo deletado: {recording.path_local}")
                else:
                    print(f"Arquivo não encontrado (já deletado?): {recording.path_local}")
            except Exception as e:
                errors_count += 1
                print(f"Erro ao deletar arquivo {recording.path_local}: {e}")

    # 3. Deletar o usuário do banco
    # Devido ao 'cascade="all, delete-orphan"' nos models, isso deve levar:
    # - Sessions
    # - Recordings (registros no banco)
    # - HistoricoMoradia
    # - Familiares
    # - PasswordResets
    try:
        await db.delete(target_user)
        await db.commit()
        print(f"Usuário {email} e dados relacionados removidos do banco.")
        print(f"Arquivos físicos removidos: {deleted_files_count}. Erros: {errors_count}.")
        
    except Exception as e:
        await db.rollback()
        print(f"Erro ao deletar usuário do banco: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao deletar usuário: {str(e)}"
        )

    return None # 204 No Content
