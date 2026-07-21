import json
import logging
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

import schemas
from authz import is_admin, require_owner_or_admin
from auth_router import fastapi_users
from config import settings
from database import get_async_session
from models import Bloco, Dataset, Frase, Recording, Session, User
from storage import (
    delete_from_gdrive,
    delete_from_s3,
    get_s3_object_access,
    save_to_gdrive,
    save_to_s3,
)
from upload_utils import (
    UploadTooLargeError,
    UploadValidationError,
    copy_upload_to_path,
    sanitize_audio_filename,
    validate_audio_content_type,
)


logger = logging.getLogger(__name__)
current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)
router = APIRouter(prefix="/recordings", tags=["Recordings"])

PROJECT_ROOT = Path(__file__).resolve().parent
configured_upload_dir = Path(settings.STORAGE_PATH).expanduser()
UPLOAD_DIR = (
    configured_upload_dir
    if configured_upload_dir.is_absolute()
    else PROJECT_ROOT / configured_upload_dir
)
DEFAULT_AUDIO_URL_EXPIRATION_SECONDS = 900
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _validate_recording_metadata(
    *,
    duration: float,
    sample_rate: int,
    room_tone_start: float | None,
    room_tone_end: float | None,
) -> None:
    numeric_values = [duration]
    if room_tone_start is not None:
        numeric_values.append(room_tone_start)
    if room_tone_end is not None:
        numeric_values.append(room_tone_end)
    if not all(math.isfinite(value) for value in numeric_values):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Audio timing values must be finite numbers.",
        )
    if duration <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="duration must be greater than zero.",
        )
    if not 8000 <= sample_rate <= 384000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="sample_rate must be between 8000 and 384000 Hz.",
        )
    if room_tone_start is not None and room_tone_start < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="room_tone_start must not be negative.",
        )
    if room_tone_end is not None and room_tone_end < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="room_tone_end must not be negative.",
        )
    if (
        room_tone_start is not None
        and room_tone_end is not None
        and room_tone_end < room_tone_start
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="room_tone_end must be greater than or equal to room_tone_start.",
        )
    if room_tone_end is not None and room_tone_end > duration:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="room_tone_end must not exceed duration.",
        )


def _parse_extra_info(extra_info: str | None) -> dict | None:
    if extra_info is None:
        return None
    try:
        parsed = json.loads(extra_info)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="extra_info must be valid JSON.",
        ) from error
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="extra_info must be a JSON object.",
        )
    return parsed


def _safe_local_recording_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    candidate = Path(path_value).expanduser()
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(UPLOAD_DIR.resolve(strict=False))
        return resolved
    except (OSError, ValueError):
        logger.error("Refusing to delete a recording path outside STORAGE_PATH")
        return None


async def _cleanup_recording_artifacts(recording: Recording) -> None:
    local_path = _safe_local_recording_path(recording.path_local)
    if local_path:
        try:
            await run_in_threadpool(local_path.unlink, missing_ok=True)
        except OSError:
            logger.exception("Could not delete local recording %s", local_path)
    await delete_from_s3(recording.audio_url_s3)
    await delete_from_gdrive(recording.audio_url_drive)


def _pagination_values(
    *,
    page: int,
    page_size: int,
    limit: int | None,
    offset: int | None,
) -> tuple[int, int, int]:
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page must be greater than or equal to 1.",
        )
    if page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"page_size must be between 1 and {MAX_PAGE_SIZE}.",
        )
    if limit is not None and (limit < 1 or limit > MAX_PAGE_SIZE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"limit must be between 1 and {MAX_PAGE_SIZE}.",
        )
    if offset is not None and offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="offset must not be negative.",
        )
    effective_page_size = limit or page_size
    effective_offset = offset if offset is not None else (page - 1) * effective_page_size
    effective_page = (effective_offset // effective_page_size) + 1
    return effective_page, effective_page_size, effective_offset


async def _resolve_user_filter(
    *,
    db: AsyncSession,
    user: User,
    user_id: uuid.UUID | None,
    latest_session: bool,
) -> uuid.UUID | None:
    if user_id is None:
        return user.id if latest_session or not user.is_superuser else None
    if user_id != user.id and not is_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access recordings from another user.",
        )
    target_user = await db.get(User, user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return user_id


async def _latest_session_id_for_user(
    *,
    db: AsyncSession,
    user_id: uuid.UUID,
) -> int | None:
    result = await db.execute(
        select(Session.id)
        .where(Session.user_id == user_id)
        .order_by(Session.started_at.desc(), Session.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _recording_audio_response(
    recording: Recording,
) -> schemas.RecordingAudioRead:
    audio_url = None
    audio_source = None
    access = None
    if recording.audio_url_s3:
        access = await get_s3_object_access(
            recording.audio_url_s3,
            DEFAULT_AUDIO_URL_EXPIRATION_SECONDS,
        )
        audio_url = access.url
        audio_source = "s3" if audio_url else None
    if audio_url is None and recording.path_local:
        audio_url = f"/admin/recordings/{recording.id_recordings}/play"
        audio_source = "local"

    return schemas.RecordingAudioRead(
        id_recordings=recording.id_recordings,
        session_id=recording.session_id,
        dataset_id=recording.dataset_id,
        bloco_id=recording.bloco_id,
        frase_id=recording.frase_id,
        duration=recording.duration,
        format=recording.format,
        sample_rate=recording.sample_rate,
        frase_content=recording.frase_content,
        is_test=recording.is_test,
        created_at=recording.created_at,
        audio_url=audio_url,
        audio_source=audio_source,
        audio_available=bool(audio_url),
        expires_in=access.expires_in if access else None,
        mime_type=access.content_type if access else recording.format,
        size_bytes=access.size_bytes if access else None,
    )


async def _recording_audio_access_or_error(
    recording: Recording,
) -> schemas.RecordingAudioAccessResponse:
    access = await get_s3_object_access(
        recording.audio_url_s3,
        DEFAULT_AUDIO_URL_EXPIRATION_SECONDS,
    )
    if access.unavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audio storage is temporarily unavailable.",
        )
    if not access.available:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file not found.",
        )
    return schemas.RecordingAudioAccessResponse(
        recording_id=recording.id_recordings,
        audio_available=True,
        audio_url=access.url,
        expires_in=access.expires_in,
        mime_type=access.content_type,
        size_bytes=access.size_bytes,
        created_at=recording.created_at,
    )


def _recording_detail_response(recording: Recording) -> schemas.RecordingDetailRead:
    return schemas.RecordingDetailRead(
        id_recordings=recording.id_recordings,
        session_id=recording.session_id,
        dataset_id=recording.dataset_id,
        bloco_id=recording.bloco_id,
        frase_id=recording.frase_id,
        is_test=recording.is_test,
        duration=recording.duration,
        format=recording.format,
        sample_rate=recording.sample_rate,
        frase_content=recording.frase_content,
        room_tone_start=recording.room_tone_start,
        room_tone_end=recording.room_tone_end,
        created_at=recording.created_at,
        extra_info=recording.extra_info,
        session_started_at=recording.session.started_at if recording.session else None,
        session_status=recording.session.status if recording.session else None,
        user_id=recording.session.user_id,
        dataset_name=recording.dataset.name if recording.dataset else None,
        dataset_type=recording.dataset.dataset_type if recording.dataset else None,
        bloco_nome=recording.bloco.nome_bloco if recording.bloco else None,
        bloco_tipo=recording.bloco.tipo if recording.bloco else None,
        frase_texto=recording.frase.texto if recording.frase else None,
    )


@router.get(
    "/sessions/{session_id}/audios",
    response_model=list[schemas.RecordingAudioRead],
)
async def get_session_audios_for_admin(
    session_id: int,
    user: User = Depends(current_superuser),
    db: AsyncSession = Depends(get_async_session),
):
    del user
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )

    result = await db.execute(
        select(Recording)
        .where(Recording.session_id == session_id)
        .order_by(Recording.created_at, Recording.id_recordings)
    )
    return [
        await _recording_audio_response(recording)
        for recording in result.scalars().all()
    ]


@router.get("", response_model=schemas.RecordingListResponse)
async def list_recordings(
    recording_id: int | None = None,
    session_id: int | None = None,
    user_id: uuid.UUID | None = None,
    latest_session: bool = False,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int | None = None,
    offset: int | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    order: Literal["asc", "desc"] = "desc",
    has_audio: bool | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    if created_from and created_to and created_to < created_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="created_to must be greater than or equal to created_from.",
        )
    effective_page, effective_page_size, effective_offset = _pagination_values(
        page=page,
        page_size=page_size,
        limit=limit,
        offset=offset,
    )
    target_user_id = await _resolve_user_filter(
        db=db,
        user=user,
        user_id=user_id,
        latest_session=latest_session,
    )
    if latest_session:
        if target_user_id is None:
            target_user_id = user.id
        latest_session_id = await _latest_session_id_for_user(
            db=db,
            user_id=target_user_id,
        )
        if latest_session_id is None:
            return schemas.RecordingListResponse(
                total=0,
                page=effective_page,
                page_size=effective_page_size,
                items=[],
            )
        session_id = latest_session_id

    conditions = []
    if recording_id is not None:
        conditions.append(Recording.id_recordings == recording_id)
    if session_id is not None:
        conditions.append(Recording.session_id == session_id)
    if target_user_id is not None:
        conditions.append(Session.user_id == target_user_id)
    if created_from is not None:
        conditions.append(Recording.created_at >= created_from)
    if created_to is not None:
        conditions.append(Recording.created_at <= created_to)
    if status_filter is not None:
        conditions.append(Session.status == status_filter)
    if has_audio is True:
        conditions.append(Recording.audio_url_s3.is_not(None))
    elif has_audio is False:
        conditions.append(Recording.audio_url_s3.is_(None))

    base_query = select(Recording).join(Session)
    count_query = select(func.count(Recording.id_recordings)).join(Session)
    for condition in conditions:
        base_query = base_query.where(condition)
        count_query = count_query.where(condition)

    ordering = (
        (Recording.created_at.asc(), Recording.id_recordings.asc())
        if order == "asc"
        else (Recording.created_at.desc(), Recording.id_recordings.desc())
    )
    result = await db.execute(
        base_query.order_by(*ordering).offset(effective_offset).limit(effective_page_size)
    )
    total = (await db.execute(count_query)).scalar_one()
    return schemas.RecordingListResponse(
        total=total,
        page=effective_page,
        page_size=effective_page_size,
        items=[
            await _recording_audio_response(recording)
            for recording in result.scalars().all()
        ],
    )


@router.get("/{recording_id}/audio", response_model=schemas.RecordingAudioAccessResponse)
async def get_recording_audio(
    recording_id: int,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    query = select(Recording).join(Session).where(Recording.id_recordings == recording_id)
    if not is_admin(user):
        query = query.where(Session.user_id == user.id)
    result = await db.execute(query)
    recording = result.scalar_one_or_none()
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not found.",
        )
    return await _recording_audio_access_or_error(recording)


@router.get("/{recording_id}/details", response_model=schemas.RecordingDetailRead)
async def get_recording_details(
    recording_id: int,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(Recording)
        .options(
            selectinload(Recording.session),
            selectinload(Recording.dataset),
            selectinload(Recording.bloco),
            selectinload(Recording.frase),
        )
        .where(Recording.id_recordings == recording_id)
    )
    recording = result.scalar_one_or_none()
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not found.",
        )
    require_owner_or_admin(user, recording.session.user_id)
    return _recording_detail_response(recording)


@router.post("", response_model=schemas.RecordingRead, status_code=status.HTTP_201_CREATED)
async def create_recording(
    audio_file: UploadFile = File(...),
    session_id: int = Form(...),
    dataset_id: int = Form(...),
    bloco_id: int = Form(...),
    frase_id: int | None = Form(None),
    duration: float = Form(...),
    format: str = Form(..., min_length=1, max_length=10),
    sample_rate: int = Form(...),
    frase_content: str | None = Form(None),
    room_tone_start: float | None = Form(None),
    room_tone_end: float | None = Form(None),
    is_test: bool = Form(False),
    extra_info: str | None = Form(None),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    _validate_recording_metadata(
        duration=duration,
        sample_rate=sample_rate,
        room_tone_start=room_tone_start,
        room_tone_end=room_tone_end,
    )
    parsed_extra_info = _parse_extra_info(extra_info)

    try:
        safe_client_filename = sanitize_audio_filename(audio_file.filename)
        validate_audio_content_type(audio_file.content_type)
    except UploadValidationError as error:
        await audio_file.close()
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(error),
        ) from error

    db_session = await db.get(Session, session_id)
    if not db_session or db_session.user_id != user.id:
        await audio_file.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or does not belong to the user.",
        )
    if db_session.finished_at is not None or db_session.status != "active":
        await audio_file.close()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot add recordings to a session that is not active.",
        )
    if not db_session.termos:
        await audio_file.close()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recording consent was not accepted for this session.",
        )
    if db_session.dataset_id != dataset_id:
        await audio_file.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="dataset_id must match the session dataset.",
        )

    db_dataset = await db.get(Dataset, dataset_id)
    if not db_dataset:
        await audio_file.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with id {dataset_id} not found.",
        )
    db_bloco = await db.get(Bloco, bloco_id)
    if not db_bloco:
        await audio_file.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bloco with id {bloco_id} not found.",
        )
    if frase_id is not None:
        db_frase = await db.get(Frase, frase_id)
        if not db_frase:
            await audio_file.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Frase with id {frase_id} not found.",
            )
        if db_frase.bloco_id != bloco_id:
            await audio_file.close()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="frase_id does not belong to the provided bloco_id.",
            )

    local_path: Path | None = None
    s3_reference: str | None = None
    drive_file_id: str | None = None
    committed = False
    try:
        new_recording = Recording(
            session_id=session_id,
            dataset_id=dataset_id,
            bloco_id=bloco_id,
            frase_id=frase_id,
            path_local=None,
            audio_url_drive=None,
            audio_url_s3=None,
            duration=duration,
            format=format.lower(),
            sample_rate=sample_rate,
            frase_content=frase_content,
            room_tone_start=room_tone_start,
            room_tone_end=room_tone_end,
            is_test=is_test,
            extra_info=parsed_extra_info,
        )
        db.add(new_recording)
        await db.flush()

        now = datetime.now(timezone.utc)
        date_path = UPLOAD_DIR / str(now.year) / f"{now.month:02d}" / f"{now.day:02d}"
        extension = Path(safe_client_filename).suffix
        final_filename = f"{new_recording.id_recordings}{extension}"
        local_path = date_path / final_filename
        await copy_upload_to_path(
            audio_file,
            local_path,
            max_bytes=settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024,
        )
        new_recording.path_local = str(local_path)

        storage_version = uuid.uuid4().hex
        s3_key = (
            f"akcit_datasets/{db_dataset.dataset_type}/{dataset_id}/"
            f"recordings/{new_recording.id_recordings}_{storage_version}{extension}"
        )
        uploaded_s3_url = await save_to_s3(str(local_path), s3_key)
        if uploaded_s3_url:
            s3_reference = s3_key
            new_recording.audio_url_s3 = s3_key
        else:
            logger.warning(
                "Recording %s was stored locally but could not be mirrored to S3",
                new_recording.id_recordings,
            )

        try:
            drive_file_id = await save_to_gdrive(str(local_path), final_filename)
        except HTTPException as error:
            logger.warning("Google Drive upload skipped: %s", error.detail)
        if drive_file_id:
            new_recording.audio_url_drive = (
                f"https://drive.google.com/file/d/{drive_file_id}/view"
            )

        await db.commit()
        committed = True
        return new_recording
    except UploadTooLargeError as error:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(error),
        ) from error
    except UploadValidationError as error:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except HTTPException:
        await db.rollback()
        raise
    except Exception as error:
        await db.rollback()
        logger.exception("Could not create recording for session %s", session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not persist the recording.",
        ) from error
    finally:
        await audio_file.close()
        # If commit failed, compensate resources created outside the database.
        if local_path is not None and not committed:
            local_path.unlink(missing_ok=True)
            await delete_from_s3(s3_reference)
            await delete_from_gdrive(drive_file_id)


@router.get("/{recording_id}", response_model=schemas.RecordingRead)
async def get_recording(
    recording_id: int,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    result = await db.execute(
        select(Recording)
        .join(Session)
        .options(selectinload(Recording.session))
        .where(Recording.id_recordings == recording_id)
    )
    recording = result.scalar_one_or_none()
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not found.",
        )
    require_owner_or_admin(user, recording.session.user_id)
    return recording


@router.delete("/delete_my_recordings", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_recordings(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user.id)
        .options(selectinload(Session.recordings))
    )
    sessions = result.scalars().all()
    recordings = [recording for session in sessions for recording in session.recordings]
    if not recordings:
        return None

    try:
        for recording in recordings:
            await db.delete(recording)
        await db.commit()
    except Exception as error:
        await db.rollback()
        logger.exception("Could not delete recordings for user %s", user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete recordings.",
        ) from error

    # External resources are cleaned only after the database commit so a failed
    # transaction never leaves live rows pointing at files we already removed.
    for recording in recordings:
        await _cleanup_recording_artifacts(recording)
    return None
