import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Tuple
import functools
import mimetypes

from fastapi import UploadFile, HTTPException, status
from fastapi.concurrency import run_in_threadpool

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from config import settings

async def get_gdrive_service():
    """
    Creates and returns a Google Drive service object using OAuth 2.0 credentials.
    This function is now async and runs blocking I/O in a thread pool.
    """
    creds = None
    
    if os.path.exists(settings.GDRIVE_OAUTH_TOKEN_FILE):
        creds = await run_in_threadpool(
            Credentials.from_authorized_user_file, 
            settings.GDRIVE_OAUTH_TOKEN_FILE, 
            scopes=["https://www.googleapis.com/auth/drive"]
        )
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Run the blocking refresh operation in a thread pool
            await run_in_threadpool(creds.refresh, Request())
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Google Drive credentials are missing or invalid. Please run generate_token.py to authenticate."
            )
        
        # Save the possibly refreshed credentials
        with open(settings.GDRIVE_OAUTH_TOKEN_FILE, 'w') as token:
            await run_in_threadpool(token.write, creds.to_json())

    try:
        # The build function is also blocking and should be run in a thread pool
        service = await run_in_threadpool(build, 'drive', 'v3', credentials=creds)
        return service
    except HttpError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while building the Google Drive service: {error}"
        )

async def save_to_gdrive(file_path: str, file_name: str) -> str:
    """
    Uploads a file to the specified Google Drive folder and returns the file ID.
    """
    if not settings.GDRIVE_FOLDER_ID or "your_google_drive_folder_id" in settings.GDRIVE_FOLDER_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Drive Folder ID is not configured in the .env file."
        )

    try:
        service = await get_gdrive_service()
        
        file_metadata = {
            'name': file_name,
            'parents': [settings.GDRIVE_FOLDER_ID]
        }
        mimetype, _ = mimetypes.guess_type(file_path)
        if mimetype is None:
            mimetype = "application/octet-stream"
        
        media = MediaFileUpload(file_path, mimetype=mimetype, resumable=True)
        
        # The execute() call is blocking I/O
        create_request = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        )
        file = await run_in_threadpool(create_request.execute)
        
        print(f"File '{file_name}' uploaded to Google Drive with ID: {file.get('id')}")
        return file.get('id')
    except HttpError as error:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to upload file to Google Drive: {error}"
        )
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during Google Drive upload: {e}"
        )

async def save_audio_file(
    audio_file: UploadFile,
    id_audio: int,
    dataset: str,
) -> Tuple[str, str]:
    """
    Orchestrates saving the audio file locally and then uploading to Google Drive.
    """
    file_extension = Path(audio_file.filename).suffix or ".webm"
    file_name = f"{id_audio}{file_extension}"
    
    storage_dir = Path(settings.STORAGE_PATH) / dataset
    os.makedirs(storage_dir, exist_ok=True)
    local_file_path = storage_dir / file_name

    with open(local_file_path, "wb") as buffer:
        shutil.copyfileobj(audio_file.file, buffer)

    drive_file_id = await save_to_gdrive(str(local_file_path), file_name)

    return str(local_file_path), drive_file_id
