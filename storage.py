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
import boto3
from botocore.exceptions import ClientError

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

async def save_to_gdrive(file_path: str, file_name: str) -> str | None:
    """
    Uploads a file to the specified Google Drive folder and returns the file ID.
    Returns None if the upload fails.
    """
    if not settings.GDRIVE_FOLDER_ID or "your_google_drive_folder_id" in settings.GDRIVE_FOLDER_ID:
        print("!!!!!!!!!!!!!!! AVISO: Google Drive Folder ID não está configurado. !!!!!!!!!!!!!!!")
        return None

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
    except (HttpError, Exception) as e:
        print(f"!!!!!!!!!!!!!!! AVISO: Falha no upload para o Google Drive. !!!!!!!!!!!!!!!")
        print(f"Erro: {e}")
        # We don't remove the local file here anymore, as the caller might need it.
        return None

async def save_to_s3(file_path: str, s3_key: str) -> str | None:
    """
    Uploads a file to the configured S3 bucket and returns the public URL.
    Returns None if the upload fails.
    """
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        bucket_name = "ermis-datasets"

        print("UPLOAD S3 DEBUG")
        print("FILE PATH:", file_path)
        print("S3 KEY:", s3_key)
        print("BUCKET:", bucket_name)


        # Boto3 operations are blocking, run them in a thread pool
        await run_in_threadpool(
            s3_client.upload_file,
            Filename=file_path,
            Bucket=bucket_name,
            Key=s3_key
        )
        
        # Construct the public URL for the object
        s3_url = f"https://{bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"
        print(f"File uploaded to S3 at: {s3_url}")
        

        return s3_url
    except (ClientError, Exception) as e:
        print(f"!!!!!!!!!!!!!!! AVISO: Falha no upload para o S3. !!!!!!!!!!!!!!!")
        print(f"Erro: {e}")
        return None

async def get_s3_presigned_url(s3_url: str, expiration: int = 3600) -> str | None:
    """
    Generate a presigned URL for an S3 object.
    """
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        bucket_name = "ermis-datasets"
        
        # Extract object key from URL
        # URL format: https://bucket-name.s3.region.amazonaws.com/object-key
        prefix = f"https://{bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/"
        if s3_url.startswith(prefix):
            object_key = s3_url[len(prefix):]
        else:
            # Fallback if URL format is different
            print(f"URL did not match expected prefix: {s3_url}")
            return None

        # The generate_presigned_url function can be fast, but we run in threadpool just in case
        response = await run_in_threadpool(
            s3_client.generate_presigned_url,
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_key},
            ExpiresIn=expiration
        )
        return response
    except Exception as e:
        print(f"Erro ao gerar URL presigned para {s3_url}: {e}")
        return None

async def save_audio_file(
    audio_file: UploadFile,
    id_audio: int,
    dataset: str,
) -> Tuple[str, str]:
    """
    Orchestrates saving the audio file locally and then uploading to Google Drive.
    """
    original_extension = Path(audio_file.filename).suffix
    file_name = f"{id_audio}{original_extension}"
    
    storage_dir = Path(settings.STORAGE_PATH) / dataset
    os.makedirs(storage_dir, exist_ok=True)
    local_file_path = storage_dir / file_name

    with open(local_file_path, "wb") as buffer:
        shutil.copyfileobj(audio_file.file, buffer)

    drive_file_id = await save_to_gdrive(str(local_file_path), file_name)

    return str(local_file_path), drive_file_id
