
from typing import List
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import func

from database import get_async_session
from models import Session, User, Recording
import schemas
from auth_router import fastapi_users
current_active_user = fastapi_users.current_user(active=True)

router = APIRouter(prefix="/sessions", tags=["Sessions"])

@router.post("", response_model=schemas.SessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_data: schemas.SessionCreate,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Creates a new recording session for the authenticated user.
    """
    # Check for an existing active session
    active_session_result = await db.execute(
        select(Session).where(Session.user_id == user.id, Session.finished_at == None)
    )
    if active_session_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active session already exists for this user.",
        )

    new_session = Session(
        user_id=user.id,
        **session_data.dict(),
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    return new_session

@router.patch("/{session_id}/finish", response_model=schemas.SessionRead)
async def finish_session(
    session_id: int,
    session_data: schemas.SessionFinish,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Finishes an active recording session.
    """
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == user.id)
    )
    db_session = result.scalars().first()

    if not db_session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    
    if db_session.finished_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session is already finished")

    if session_data.finished_at <= db_session.started_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Finish time must be after start time")

    db_session.finished_at = session_data.finished_at
    if session_data.notes:
        db_session.notes = session_data.notes
        
    await db.commit()
    await db.refresh(db_session)
    return db_session

@router.get("/active-{user_id}", response_model=List[schemas.SessionList])
async def get_user_sessions(
    user_id: uuid.UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Gets all sessions for a specific user.
    """
    if user_id != user.id:
        # In a real app, you might check for admin roles here
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
        session_dict = s.__dict__
        session_dict["recordings_count"] = len(s.recordings)
        session_dict["status"] = "active" if s.finished_at is None else "finished"
        sessions_with_counts.append(schemas.SessionList.from_orm(s))
        
    return sessions_with_counts
