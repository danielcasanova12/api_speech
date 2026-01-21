import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import (APIRouter, Depends, File, Form, Header, HTTPException,
                     UploadFile, status)

from models import (RecordingUploadResponse, SessionCreateRequest,
                    SessionCreateResponse, StatusResponse, SectionCreateRequest, 
                    SectionCreateResponse, DeleteResponse)
from security import basic_auth
from storage import save_audio_file
from validations import validate_audio, get_audio_duration
from database import add_recording, add_section

api_router = APIRouter()


class RecordingForm:
    def __init__(
        self,
        nomedataset: str = Form(...),
        id_secao: int = Form(...),
        emocao: str = Form(...),
        format: Optional[str] = Form(None),
    ):
        self.nomedataset = nomedataset
        self.id_secao = id_secao
        self.emocao = emocao
        self.format = format


@api_router.post(
    "/recordings",
    response_model=RecordingUploadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Recordings"],
)
async def upload_recording(
    audio: UploadFile = File(...),
    form_data: RecordingForm = Depends(),
    current_user: dict = Depends(basic_auth),
):
    """
    Receives a complete audio recording and its metadata.
    """
    # Validate form data and audio file
    await validate_audio(audio)

    # Generate a unique ID for the recording
    recording_id = f"{form_data.nomedataset}_{uuid.uuid4().hex[:12]}"

    # Save the file to local storage and Google Drive
    saved_path, drive_file_id = await save_audio_file(
        audio_file=audio,
        recording_id=recording_id,
        nomedataset=form_data.nomedataset,
    )

    # Save metadata to the database
    uploaded_at = datetime.utcnow()
    add_recording(
        id=recording_id,
        nomedataset=form_data.nomedataset,
        id_secao=form_data.id_secao,
        emocao=form_data.emocao,
        created_at=uploaded_at.isoformat(),
    )

    return RecordingUploadResponse(
        fileId=recording_id,
        driveFileId=drive_file_id,
        uploadedAt=uploaded_at,
    )


@api_router.post("/sessions", response_model=SessionCreateResponse, status_code=status.HTTP_201_CREATED, tags=["Sessions"])
async def create_session(
    session_data: SessionCreateRequest,
    current_user: dict = Depends(basic_auth),
):
    """
    Creates a new recording session.
    """
    if current_user.get("sub") != session_data.userId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User ID does not match token subject",
        )
        
    session_id = str(uuid.uuid4())
    # In a real app, you would save the session to a database here
    return SessionCreateResponse(
        sessionId=session_id,
        createdAt=datetime.utcnow(),
    )


@api_router.post("/sections", response_model=SectionCreateResponse, status_code=status.HTTP_201_CREATED, tags=["Sections"])
async def create_section(
    section_data: SectionCreateRequest,
    current_user: dict = Depends(basic_auth),
):
    """
    Creates a new section.
    """
    section_id = add_section(
        gender=section_data.gender,
        dataset_type=section_data.dataset_type,
    )
    return SectionCreateResponse(
        section_id=section_id,
    )
