import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import (APIRouter, Depends, File, Form, Header, HTTPException,
                     UploadFile, status)

from models import (RecordingUploadResponse, SessionCreate, SessionResponse)
from security import basic_auth
from storage import save_audio_file
from validations import validate_audio, get_audio_duration
from database import add_recording, add_session, get_session_by_id

api_router = APIRouter()


@api_router.post(
    "/recordings",
    response_model=RecordingUploadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Recordings"],
)
async def upload_recording(
    audio: UploadFile = File(...),
    id_session: int = Form(...),
    emocao: str = Form(...),
    claimed_duration: float = Form(...), # Added claimed_duration
    current_user: dict = Depends(basic_auth),
):
    """
    Receives an audio recording and its metadata, associating it with an existing session.
    """
    # Validate audio file
    await validate_audio(audio, claimed_duration) # Pass claimed_duration

    # Get session details to retrieve the dataset
    session = get_session_by_id(id_session)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID {id_session} not found."
        )
    dataset = session["dataset"]

    # Add recording metadata to the database first to get id_audio
    id_audio = add_recording(
        id_session=id_session,
        emotion=emocao,
    )

    # Save the file to local storage and Google Drive
    saved_path, drive_file_id = await save_audio_file(
        audio_file=audio,
        id_audio=id_audio,
        dataset=dataset,
    )

    uploaded_at = datetime.utcnow()

    return RecordingUploadResponse(
        id_audio=id_audio,
        file_path=saved_path,
        uploadedAt=uploaded_at,
    )


@api_router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED, tags=["Sessions"])
async def create_session(
    session_data: SessionCreate,
    current_user: dict = Depends(basic_auth),
):
    """
    Creates a new recording session.
    """
    session_id = add_session(
        gender=session_data.genero,
        dataset=session_data.dataset,
    )
    return SessionResponse(
        id=session_id,
        genero=session_data.genero,
        dataset=session_data.dataset,
    )