
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
import shutil
from pathlib import Path

from database import get_async_session
from models import Session, User, Recording, Dataset
import schemas
from auth_router import fastapi_users
current_active_user = fastapi_users.current_user(active=True)

router = APIRouter(prefix="/recordings", tags=["Recordings"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@router.post("", response_model=schemas.RecordingRead, status_code=status.HTTP_201_CREATED)
async def create_recording(
    audio_file: UploadFile = File(...),
    session_id: int = Form(...),
    dataset_id: int = Form(...),
    duration: float = Form(...),
    format: str = Form(...),
    sample_rate: int = Form(...),
    text_content: str = Form(None),
    espontaniedade: str = Form(None),
    emocao: str = Form(None),
    room_tone_start: bool = Form(None),
    room_tone_end: bool = Form(None),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Creates a new audio recording.
    """
    # 1. Validate session and eagerly load recordings
    result = await db.execute(
        select(Session)
        .options(selectinload(Session.recordings))
        .where(Session.id == session_id, Session.user_id == user.id)
    )
    db_session = result.scalars().first()

    if not db_session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found or does not belong to the user.")
    
    if db_session.finished_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot add recordings to a finished session.")

    # 2. Save the file locally
    file_extension = Path(audio_file.filename).suffix
    # Now this access is safe and won't trigger a lazy load
    file_path = UPLOAD_DIR / f"{session_id}_{len(db_session.recordings) + 1}{file_extension}"
    
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
    finally:
        audio_file.file.close()

    # 3. Create recording entry in the database
    new_recording = Recording(
        session_id=session_id,
        dataset_id=dataset_id,
        path_local=str(file_path),
        duration=duration,
        format=format,
        sample_rate=sample_rate,
        text_content=text_content,
        espontaniedade=espontaniedade,
        emocao=emocao,
        room_tone_start=room_tone_start,
        room_tone_end=room_tone_end
        # URLs for Drive/S3 would be updated by a background task
    )
    
    db.add(new_recording)
    await db.commit()
    await db.refresh(new_recording)
    
    return new_recording
