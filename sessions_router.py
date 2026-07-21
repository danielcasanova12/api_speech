from typing import List
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from authz import is_admin, require_owner_or_admin
from database import get_async_session
from models import Recording, Session, User, Dataset
import schemas
from auth_router import fastapi_users
from emails import send_session_status_email
from storage import get_s3_object_access

current_active_user = fastapi_users.current_user(active=True)

router = APIRouter(prefix="/sessions", tags=["Sessions"])

SESSION_STATUSES = {"active", "finished", "cancelled"}
TERMINAL_SESSION_STATUSES = {"finished", "cancelled"}
DEFAULT_AUDIO_URL_EXPIRATION_SECONDS = 900
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _as_utc(value: datetime) -> datetime:
    """Normalize persisted timestamps; PostgreSQL values should already be aware."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _effective_session_status(db_session: Session) -> str:
    current_status = db_session.status or "active"
    if db_session.finished_at is not None and current_status == "active":
        return "finished"
    return current_status


def _pagination_values(page: int, page_size: int) -> tuple[int, int]:
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
    return page, page_size


async def _recording_audio_response(recording: Recording) -> schemas.RecordingAudioRead:
    access = await get_s3_object_access(
        recording.audio_url_s3,
        DEFAULT_AUDIO_URL_EXPIRATION_SECONDS,
    )
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
        audio_url=access.url,
        audio_source="s3" if access.url else None,
        audio_available=access.available,
        expires_in=access.expires_in,
        mime_type=access.content_type,
        size_bytes=access.size_bytes,
    )


def _session_list_response(db_session: Session) -> schemas.SessionList:
    session_payload = schemas.SessionRead.model_validate(db_session).model_dump()
    session_payload["recordings_count"] = (
        len(db_session.recordings) if db_session.recordings else 0
    )
    session_payload["status"] = _effective_session_status(db_session)
    return schemas.SessionList.model_validate(session_payload)


def _prepare_session_update(
    db_session: Session,
    session_data: schemas.SessionUpdate,
    *,
    now: datetime | None = None,
) -> tuple[dict, str, bool]:
    """Validate the state transition and return data ready for persistence."""
    now = _as_utc(now or datetime.now(timezone.utc))
    update_data = session_data.model_dump(exclude_unset=True)
    provided_fields = session_data.model_fields_set
    current_status = _effective_session_status(db_session)

    if current_status not in SESSION_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session has an invalid persisted status: {current_status}",
        )

    if "status" in provided_fields and session_data.status is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session status cannot be null",
        )

    if "finished_at" in provided_fields and session_data.finished_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="finished_at cannot be cleared or set to null",
        )

    requested_status = update_data.get("status", current_status)
    explicit_finished_at = "finished_at" in provided_fields

    if current_status in TERMINAL_SESSION_STATUSES:
        if requested_status != current_status:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A finished or cancelled session cannot change status",
            )

        if explicit_finished_at and db_session.finished_at is not None:
            requested_finished_at = _as_utc(update_data["finished_at"])
            if requested_finished_at != _as_utc(db_session.finished_at):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A terminal session's finish time cannot be changed",
                )

        # Repair legacy terminal rows that were saved without a finish time.
        if db_session.finished_at is None:
            finished_at = _as_utc(update_data.get("finished_at", now))
            if finished_at <= _as_utc(db_session.started_at):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Finish time must be after start time",
                )
            update_data["finished_at"] = finished_at

        return update_data, current_status, False

    # Preserve the previous PUT contract: supplying only finished_at finishes
    # an active session, but never leaves status='active' with a finish time.
    if explicit_finished_at and "status" not in provided_fields:
        requested_status = "finished"
        update_data["status"] = requested_status

    if requested_status == "active" and explicit_finished_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An active session cannot have finished_at",
        )

    if requested_status in TERMINAL_SESSION_STATUSES:
        finished_at = update_data.get("finished_at", now)
        finished_at = _as_utc(finished_at)
        if finished_at <= _as_utc(db_session.started_at):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Finish time must be after start time",
            )
        update_data["status"] = requested_status
        update_data["finished_at"] = finished_at

    return update_data, requested_status, requested_status in TERMINAL_SESSION_STATUSES

@router.post("", response_model=schemas.SessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_data: schemas.SessionCreate,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Creates a new recording session for the authenticated user.
    If an active session for the user and dataset already exists, it returns the existing session.
    """
    # Check if the provided dataset_id exists
    dataset = await db.get(Dataset, session_data.dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with id {session_data.dataset_id} not found.",
        )

    # Check for any existing active session for the user, regardless of the dataset
    active_session_result = await db.execute(
        select(Session).where(
            Session.user_id == user.id,
            Session.finished_at.is_(None),
            or_(Session.status == "active", Session.status.is_(None)),
        )
    )
    existing_session = active_session_result.scalars().first()
    if existing_session:
        existing_session_data = (
            schemas.SessionRead.model_validate(existing_session).model_dump(mode='json')
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "An active session already exists for this user.",
                "session": existing_session_data,
            },
        )

    new_session = Session(
        user_id=user.id,
        **session_data.model_dump(exclude_unset=True),
        status="active",
        numero_frase=1,
    )
    db.add(new_session)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        conflicting_result = await db.execute(
            select(Session).where(
                Session.user_id == user.id,
                Session.finished_at.is_(None),
                or_(Session.status == "active", Session.status.is_(None)),
            )
        )
        conflicting_session = conflicting_result.scalars().first()
        detail: dict[str, object] = {
            "message": "An active session already exists for this user."
        }
        if conflicting_session is not None:
            detail["session"] = schemas.SessionRead.model_validate(
                conflicting_session
            ).model_dump(mode="json")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        ) from error
    return new_session

@router.put("/{session_id}", response_model=schemas.SessionRead)
async def update_session(
    session_id: int,
    session_data: schemas.SessionUpdate,
    background_tasks: BackgroundTasks,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Updates a session and sends email on finish/cancel.
    """
    result = await db.execute(
        select(Session)
        .options(selectinload(Session.dataset), selectinload(Session.recordings))
        .where(Session.id == session_id, Session.user_id == user.id)
    )
    db_session = result.scalars().first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    update_data, new_status, should_send_email = _prepare_session_update(
        db_session, session_data
    )
    for key, value in update_data.items():
        setattr(db_session, key, value)

    dataset_name = db_session.dataset.name if db_session.dataset else "Desconhecido"
    recordings_count = len(db_session.recordings) if db_session.recordings else 0

    await db.commit()

    # Enviar Email em Background (não trava a resposta da API)
    if should_send_email:
        background_tasks.add_task(
            send_session_status_email,
            to_email=user.email,
            user_name=user.nome_completo,
            dataset_name=dataset_name,
            status=new_status,
            started_at=db_session.started_at,
            finished_at=db_session.finished_at,
            recordings_count=recordings_count,
        )

    return db_session


@router.get("/recent", response_model=schemas.RecentSessionsResponse)
async def get_recent_sessions(
    dataset_id: int | None = Query(default=None, gt=0),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    page, page_size = _pagination_values(page, page_size)
    if created_from and created_to and created_to < created_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="created_to must be greater than or equal to created_from.",
        )
    if dataset_id is not None and await db.get(Dataset, dataset_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with id {dataset_id} not found.",
        )

    conditions = []
    if not is_admin(user):
        conditions.append(Session.user_id == user.id)
    if dataset_id is not None:
        conditions.append(Session.dataset_id == dataset_id)
    if created_from is not None:
        conditions.append(Session.started_at >= created_from)
    if created_to is not None:
        conditions.append(Session.started_at <= created_to)

    query = select(Session).options(selectinload(Session.recordings))
    count_query = select(func.count(Session.id))
    for condition in conditions:
        query = query.where(condition)
        count_query = count_query.where(condition)

    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(Session.started_at.desc(), Session.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    total = (await db.execute(count_query)).scalar_one()
    return schemas.RecentSessionsResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_session_list_response(session) for session in result.scalars().all()],
    )


@router.get("/{session_id}/recordings", response_model=schemas.SessionRecordingsResponse)
async def get_session_recordings(
    session_id: int,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    page, page_size = _pagination_values(page, page_size)
    db_session = await db.get(Session, session_id)
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )
    require_owner_or_admin(user, db_session.user_id, hide_forbidden=False)

    offset = (page - 1) * page_size
    result = await db.execute(
        select(Recording)
        .where(Recording.session_id == session_id)
        .order_by(Recording.created_at.asc(), Recording.id_recordings.asc())
        .offset(offset)
        .limit(page_size)
    )
    total = (
        await db.execute(
            select(func.count(Recording.id_recordings)).where(
                Recording.session_id == session_id
            )
        )
    ).scalar_one()
    return schemas.SessionRecordingsResponse(
        session_id=session_id,
        user_id=db_session.user_id,
        total=total,
        page=page,
        page_size=page_size,
        items=[
            await _recording_audio_response(recording)
            for recording in result.scalars().all()
        ],
    )

@router.get("/active-{user_id}", response_model=List[schemas.SessionList]) # This endpoint returns a list
async def get_user_sessions(
    user_id: uuid.UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Gets all sessions for a specific user.
    """
    if user_id != user.id and not is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot view sessions of another user")

    result = await db.execute(
        select(Session)
        .where(Session.user_id == user_id)
        .options(selectinload(Session.recordings))
        .order_by(Session.started_at.desc())
    )
    sessions = result.scalars().all()
    
    sessions_with_counts = []
    for s in sessions:
        sessions_with_counts.append(_session_list_response(s))
        
    return sessions_with_counts
