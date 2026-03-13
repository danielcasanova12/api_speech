from datetime import datetime
import uuid
import os
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
import shutil
from pathlib import Path

from storage import save_to_gdrive, save_to_s3
from database import get_async_session
from models import Bloco, Session, User, Recording, Dataset
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
    bloco_id: int = Form(...),
    frase_id: int = Form(None),
    duration: float = Form(...),
    format: str = Form(...),
    sample_rate: int = Form(...),
    frase_content: str = Form(None),
    room_tone_start: float = Form(None),
    room_tone_end: float = Form(None),
    is_test: bool = Form(False),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Creates a new audio recording, saving it locally and uploading to Google Drive and AWS S3.
    """
    # 1. Validate session and bloco
    db_session = await db.get(Session, session_id)
    if not db_session or db_session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found or does not belong to the user.")
    
    if db_session.finished_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot add recordings to a finished session.")

    db_bloco = await db.get(Bloco, bloco_id)
    if not db_bloco:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bloco with id {bloco_id} not found.")

    # 2. Save the file locally
    today = datetime.utcnow()
    date_path = UPLOAD_DIR / str(today.year) / f"{today.month:02d}" / f"{today.day:02d}"
    date_path.mkdir(parents=True, exist_ok=True)
    
    file_extension = Path(audio_file.filename).suffix
    filename = f"{session_id}_{uuid.uuid4()}{file_extension}"
    file_path = date_path / filename
    
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
    finally:
        audio_file.file.close()

    # 3. Determine S3 folder and upload (optional)
    s3_url = None
    try:
        db_dataset = await db.get(Dataset, dataset_id)
        if not db_dataset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Dataset with id {dataset_id} not found.")
        
        dataset_name = db_dataset.name.lower()
        if 'emocao' in dataset_name or 'emoção' in dataset_name:
            s3_folder = 'emocao'
        else:
            s3_folder = 'voz_geral'
        
        s3_key = f"{s3_folder}/{filename}"
        s3_url = await save_to_s3(str(file_path), s3_key)
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: Exception in create_recording: {e}") # Temporary debug print
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    # 4. Upload to Google Drive (optional)
    drive_url = None
    try:
        drive_file_id = await save_to_gdrive(str(file_path), filename)
        drive_url = f"https://drive.google.com/file/d/{drive_file_id}/view"
    except Exception as e:
        print(f"!!!!!!!!!!!!!!! AVISO: Falha no upload para o Google Drive. !!!!!!!!!!!!!!!")
        print(f"Erro: {e}")

    # 5. Create recording entry in the database
    new_recording = Recording(
        session_id=session_id,
        dataset_id=dataset_id,
        bloco_id=bloco_id,
        frase_id=frase_id,
        path_local=str(file_path),
        audio_url_drive=drive_url,
        audio_url_s3=s3_url,
        duration=duration,
        format=format,
        sample_rate=sample_rate,
        frase_content=frase_content,
        room_tone_start=room_tone_start,
        room_tone_end=room_tone_end,
        is_test=is_test,
    )
    
    db.add(new_recording)
    await db.commit()
    await db.refresh(new_recording)
    
    return new_recording


@router.get("/{recording_id}", response_model=schemas.RecordingRead)
async def get_recording(
    recording_id: int,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Gets a specific recording by its ID.
    """
    result = await db.execute(
        select(Recording)
        .join(Session)
        .where(Recording.id_recordings == recording_id, Session.user_id == user.id)
    )
    recording = result.scalar_one_or_none()

    if not recording:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording not found.")
    
    return recording


@router.delete("/delete_my_recordings", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_recordings(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Deletes all recordings for the currently authenticated user.
    """
    # 1. Find all sessions for the user
    result = await db.execute(
        select(Session).where(Session.user_id == user.id).options(selectinload(Session.recordings))
    )
    sessions = result.scalars().all()

    recordings_to_delete = [rec for sess in sessions for rec in sess.recordings]

    if not recordings_to_delete:
        return

    # 2. Delete local files and collect db objects for deletion
    for recording in recordings_to_delete:
        if recording.path_local and os.path.exists(recording.path_local):
            try:
                os.remove(recording.path_local)
            except OSError as e:
                print(f"Error deleting file {recording.path_local}: {e}")

        # TODO: Implement deletion from Google Drive and S3
        # drive_service = await get_gdrive_service()
        # if recording.audio_url_drive:
        #     file_id = recording.audio_url_drive.split('/')[-2]
        #     await run_in_threadpool(drive_service.files().delete(fileId=file_id).execute)
        # if recording.audio_url_s3:
        #     # Add s3 deletion logic here

        await db.delete(recording)
    
    await db.commit()
