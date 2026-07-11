import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import delete, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from config import settings
from database import get_async_session
from models import Endereco, Familiar, HistoricoMoradia, User, Recording, Session
from auth_router import fastapi_users
from schemas import RecordingRead
from storage import delete_from_gdrive, delete_from_s3, get_s3_presigned_url


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecordingAssets:
    path_local: str | None
    audio_url_s3: str | None
    audio_url_drive: str | None


def _storage_roots() -> tuple[Path, ...]:
    roots: set[Path] = set()
    for configured_root in (settings.STORAGE_PATH, "uploads"):
        root = Path(configured_root).expanduser()
        if not root.is_absolute():
            root = Path.cwd() / root
        roots.add(root.resolve())
    return tuple(roots)


def _delete_local_recording(reference: str | None) -> bool:
    """Delete only regular files contained by an approved storage root."""
    if not reference:
        return True

    candidate = Path(reference).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate

    try:
        resolved = candidate.resolve()
        if not any(resolved == root or root in resolved.parents for root in _storage_roots()):
            logger.warning("Refusing to delete recording outside configured storage roots")
            return False
        if not resolved.exists():
            return True
        if not resolved.is_file():
            logger.warning("Refusing to delete non-file recording path: %s", resolved)
            return False
        resolved.unlink()
        return True
    except OSError as error:
        logger.warning("Could not delete local recording %s: %s", candidate, error)
        return False


async def _cleanup_recording_assets(recordings: list[RecordingAssets]) -> None:
    """Best-effort cleanup after the database transaction has committed."""
    for recording in recordings:
        await run_in_threadpool(_delete_local_recording, recording.path_local)
        if not await delete_from_s3(recording.audio_url_s3):
            logger.warning("Could not delete an S3 recording after database cleanup")
        if not await delete_from_gdrive(recording.audio_url_drive):
            logger.warning("Could not delete a Drive recording after database cleanup")

# Dependência para garantir que apenas superusuários acessem
current_superuser = fastapi_users.current_user(active=True, superuser=True)

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/recordings/{recording_id}/play")
async def play_recording(
    recording_id: int,
    user: User = Depends(current_superuser),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Retorna o arquivo de áudio físico ou redireciona para o S3 para ser reproduzido diretamente no Swagger ou navegador.
    Apenas superusuários.
    """
    result = await db.execute(select(Recording).where(Recording.id_recordings == recording_id))
    recording = result.scalars().first()

    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gravação não encontrada no banco de dados."
        )
    
    # Se o arquivo existir fisicamente na máquina (pasta uploads/), retorna ele.
    if recording.path_local and os.path.exists(recording.path_local):
        return FileResponse(path=recording.path_local)

    # Se não existir fisicamente, mas existir no S3, redireciona o player para a URL do S3 usando uma Presigned URL.
    if recording.audio_url_s3:
        presigned_url = await get_s3_presigned_url(recording.audio_url_s3)
        if presigned_url:
            return RedirectResponse(url=presigned_url)
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao gerar URL de acesso temporário do S3."
            )

    # Se não tem em nenhum dos dois, retorna erro.
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Arquivo de áudio não encontrado fisicamente no servidor nem no S3."
    )

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
    normalized_email = email.strip().lower()
    result = await db.execute(
        select(User.id).where(func.lower(User.email) == normalized_email)
    )
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
    normalized_email = email.strip().lower()
    result = await db.execute(
        select(User).where(func.lower(User.email) == normalized_email)
    )
    target_user = result.scalars().first()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuário com email '{normalized_email}' não encontrado."
        )

    # Não permitir que o admin se delete a si mesmo por engano (opcional, mas seguro)
    if target_user.id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode deletar sua própria conta de administrador por aqui."
        )

    # Capture external references before deleting their database rows.
    recordings_result = await db.execute(
        select(Recording)
        .join(Session)
        .where(Session.user_id == target_user.id)
    )
    recordings = recordings_result.scalars().all()
    recording_assets = [
        RecordingAssets(
            path_local=recording.path_local,
            audio_url_s3=recording.audio_url_s3,
            audio_url_drive=recording.audio_url_drive,
        )
        for recording in recordings
    ]

    address_ids = {
        target_user.cidade_nascimento_id,
        target_user.cidade_atual_id,
    }
    history_addresses = await db.execute(
        select(HistoricoMoradia.endereco_id).where(
            HistoricoMoradia.user_id == target_user.id
        )
    )
    family_addresses = await db.execute(
        select(Familiar.endereco_id).where(Familiar.user_id == target_user.id)
    )
    address_ids.update(history_addresses.scalars().all())
    address_ids.update(family_addresses.scalars().all())
    address_ids.discard(None)

    # Commit all relational deletion first. No local/cloud object is touched if
    # this transaction fails.
    try:
        await db.delete(target_user)
        await db.flush()

        if address_ids:
            referenced_by_user = select(User.id).where(
                or_(
                    User.cidade_nascimento_id == Endereco.id,
                    User.cidade_atual_id == Endereco.id,
                )
            ).exists()
            referenced_by_history = select(HistoricoMoradia.id).where(
                HistoricoMoradia.endereco_id == Endereco.id
            ).exists()
            referenced_by_family = select(Familiar.id).where(
                Familiar.endereco_id == Endereco.id
            ).exists()
            await db.execute(
                delete(Endereco).where(
                    Endereco.id.in_(address_ids),
                    ~referenced_by_user,
                    ~referenced_by_history,
                    ~referenced_by_family,
                ).execution_options(synchronize_session=False)
            )

        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Could not delete user %s from the database", target_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao deletar usuário e seus dados.",
        )

    await _cleanup_recording_assets(recording_assets)
    logger.info("Deleted user %s and %d recording rows", target_user.id, len(recordings))
    return None
