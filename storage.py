import logging
import mimetypes
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Tuple
from urllib.parse import quote, unquote, urlparse

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from config import settings
from upload_utils import (
    copy_upload_to_path,
    sanitize_audio_filename,
    validate_audio_content_type,
)


logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent
GDRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]


@dataclass(frozen=True)
class S3ObjectAccess:
    available: bool
    url: str | None = None
    expires_in: int | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    last_modified: datetime | None = None
    missing: bool = False
    unavailable: bool = False


def _configured_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def _write_credentials_atomically(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary_path.write_text(content, encoding="utf-8")
        try:
            temporary_path.chmod(0o600)
        except OSError:
            # Windows permissions are not represented by POSIX chmod bits.
            pass
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


async def get_gdrive_service():
    """Create a Google Drive client without blocking the event loop."""
    token_path = _configured_path(settings.GDRIVE_OAUTH_TOKEN_FILE)
    creds = None

    if token_path.exists():
        creds = await run_in_threadpool(
            Credentials.from_authorized_user_file,
            str(token_path),
            GDRIVE_SCOPES,
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            await run_in_threadpool(creds.refresh, Request())
            await run_in_threadpool(
                _write_credentials_atomically,
                token_path,
                creds.to_json(),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google Drive credentials are missing or invalid. Run generate_token.py to authenticate.",
            )

    try:
        return await run_in_threadpool(build, "drive", "v3", credentials=creds)
    except HttpError as error:
        logger.exception("Could not build the Google Drive client")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not connect to Google Drive.",
        ) from error


async def save_to_gdrive(file_path: str, file_name: str) -> str | None:
    """Upload a file to the configured Drive folder and return its file id."""
    folder_id = settings.GDRIVE_FOLDER_ID.strip()
    if not folder_id or folder_id.startswith("your_"):
        logger.info("Google Drive upload skipped because GDRIVE_FOLDER_ID is not configured")
        return None

    try:
        service = await get_gdrive_service()
        mimetype, _ = mimetypes.guess_type(file_path)
        media = MediaFileUpload(
            file_path,
            mimetype=mimetype or "application/octet-stream",
            resumable=True,
        )
        request = service.files().create(
            body={"name": file_name, "parents": [folder_id]},
            media_body=media,
            fields="id",
        )
        uploaded_file = await run_in_threadpool(request.execute)
        file_id = uploaded_file.get("id")
        if not file_id:
            logger.warning("Google Drive returned no file id for %s", file_name)
            return None
        logger.info("Uploaded %s to Google Drive", file_name)
        return file_id
    except HTTPException:
        raise
    except (HttpError, OSError) as error:
        logger.warning("Google Drive upload failed for %s: %s", file_name, error)
        return None
    except Exception:
        logger.exception("Unexpected Google Drive upload failure for %s", file_name)
        return None


def _gdrive_file_id(reference: str) -> str | None:
    value = reference.strip()
    if not value:
        return None
    if "/d/" in value:
        return value.split("/d/", 1)[1].split("/", 1)[0] or None
    if value.startswith("http://") or value.startswith("https://"):
        return None
    return value


async def delete_from_gdrive(reference: str | None) -> bool:
    """Best-effort deletion of a Drive object by id or canonical URL."""
    if not reference:
        return True
    file_id = _gdrive_file_id(reference)
    if not file_id:
        logger.warning("Could not extract a Google Drive id from the stored reference")
        return False
    try:
        service = await get_gdrive_service()
        request = service.files().delete(fileId=file_id)
        await run_in_threadpool(request.execute)
        return True
    except Exception as error:
        logger.warning("Could not delete Google Drive object %s: %s", file_id, error)
        return False


def _usable_aws_credentials() -> tuple[str, str] | None:
    access_key = settings.AWS_ACCESS_KEY_ID.strip()
    secret_key = settings.AWS_SECRET_ACCESS_KEY.strip()
    placeholders = ("your_", "change-me", "placeholder")
    if (
        access_key
        and secret_key
        and not access_key.lower().startswith(placeholders)
        and not secret_key.lower().startswith(placeholders)
    ):
        return access_key, secret_key
    return None


def get_s3_client():
    """Create an S3 client, allowing the normal AWS credential chain."""
    kwargs: dict[str, str] = {"region_name": settings.AWS_REGION}
    credentials = _usable_aws_credentials()
    if credentials:
        kwargs["aws_access_key_id"], kwargs["aws_secret_access_key"] = credentials
    return boto3.client("s3", **kwargs)


def _s3_object_key(reference: str) -> str | None:
    value = reference.strip()
    if not value:
        return None
    if not value.startswith(("http://", "https://")):
        return unquote(value.lstrip("/")) or None

    parsed = urlparse(value)
    hostname = (parsed.hostname or "").lower()
    bucket = settings.S3_BUCKET_NAME
    path = unquote(parsed.path.lstrip("/"))
    if hostname == f"{bucket}.s3.amazonaws.com" or hostname.startswith(
        f"{bucket}.s3."
    ):
        return path or None
    if hostname == "s3.amazonaws.com" or hostname.startswith("s3."):
        bucket_prefix = f"{bucket}/"
        return path[len(bucket_prefix) :] if path.startswith(bucket_prefix) else None
    return None


def _s3_public_url(object_key: str) -> str:
    encoded_key = quote(object_key, safe="/")
    return (
        f"https://{settings.S3_BUCKET_NAME}.s3."
        f"{settings.AWS_REGION}.amazonaws.com/{encoded_key}"
    )


async def save_to_s3(file_path: str, s3_key: str) -> str | None:
    """Upload a local file to the configured bucket and return its URL."""
    source = Path(file_path)
    object_key = s3_key.strip().lstrip("/")
    if not source.is_file():
        raise FileNotFoundError(f"Audio file not found: {source}")
    if not object_key:
        raise ValueError("S3 object key must not be empty")

    try:
        client = get_s3_client()
        await run_in_threadpool(
            client.upload_file,
            Filename=str(source),
            Bucket=settings.S3_BUCKET_NAME,
            Key=object_key,
        )
        logger.info("Uploaded %s to S3 key %s", source.name, object_key)
        return _s3_public_url(object_key)
    except (ClientError, BotoCoreError, OSError) as error:
        logger.warning("S3 upload failed for %s: %s", source, error)
        return None
    except Exception:
        logger.exception("Unexpected S3 upload failure for %s", source)
        return None


async def delete_from_s3(reference: str | None) -> bool:
    """Best-effort deletion of an S3 object by key or URL."""
    if not reference:
        return True
    object_key = _s3_object_key(reference)
    if not object_key:
        logger.warning("Stored S3 reference does not match the configured bucket")
        return False
    try:
        client = get_s3_client()
        await run_in_threadpool(
            client.delete_object,
            Bucket=settings.S3_BUCKET_NAME,
            Key=object_key,
        )
        return True
    except (ClientError, BotoCoreError, OSError) as error:
        logger.warning("Could not delete S3 key %s: %s", object_key, error)
        return False
    except Exception:
        logger.exception("Unexpected failure deleting S3 key %s", object_key)
        return False


async def get_s3_presigned_url(
    s3_reference: str,
    expiration: int = 3600,
) -> str | None:
    """Generate a temporary URL from either an object key or an S3 URL."""
    if not 1 <= expiration <= 604800:
        raise ValueError("expiration must be between 1 and 604800 seconds")
    object_key = _s3_object_key(s3_reference)
    if not object_key:
        logger.warning("Could not parse the configured S3 object reference")
        return None
    try:
        client = get_s3_client()
        return await run_in_threadpool(
            client.generate_presigned_url,
            "get_object",
            Params={"Bucket": settings.S3_BUCKET_NAME, "Key": object_key},
            ExpiresIn=expiration,
        )
    except (ClientError, BotoCoreError) as error:
        logger.warning("Could not presign S3 key %s: %s", object_key, error)
        return None
    except Exception:
        logger.exception("Unexpected failure presigning S3 key %s", object_key)
        return None


async def get_s3_object_access(
    s3_reference: str | None,
    expiration: int = 900,
) -> S3ObjectAccess:
    """Return object metadata plus a temporary URL without exposing bucket internals."""
    if not s3_reference:
        return S3ObjectAccess(available=False, missing=True)
    if not 1 <= expiration <= 604800:
        raise ValueError("expiration must be between 1 and 604800 seconds")

    object_key = _s3_object_key(s3_reference)
    if not object_key:
        logger.warning("Could not parse the configured S3 object reference")
        return S3ObjectAccess(available=False, missing=True)

    try:
        client = get_s3_client()
        metadata = await run_in_threadpool(
            client.head_object,
            Bucket=settings.S3_BUCKET_NAME,
            Key=object_key,
        )
        url = await run_in_threadpool(
            client.generate_presigned_url,
            "get_object",
            Params={"Bucket": settings.S3_BUCKET_NAME, "Key": object_key},
            ExpiresIn=expiration,
        )
        return S3ObjectAccess(
            available=True,
            url=url,
            expires_in=expiration,
            content_type=metadata.get("ContentType"),
            size_bytes=metadata.get("ContentLength"),
            last_modified=metadata.get("LastModified"),
        )
    except ClientError as error:
        error_code = str(error.response.get("Error", {}).get("Code", ""))
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            logger.warning("S3 object was not found")
            return S3ObjectAccess(available=False, missing=True)
        logger.warning("S3 is unavailable while accessing object: %s", error_code)
        return S3ObjectAccess(available=False, unavailable=True)
    except BotoCoreError as error:
        logger.warning("S3 is unavailable while accessing object: %s", error)
        return S3ObjectAccess(available=False, unavailable=True)
    except Exception:
        logger.exception("Unexpected failure accessing an S3 object")
        return S3ObjectAccess(available=False, unavailable=True)


async def save_audio_file(
    audio_file: UploadFile,
    id_audio: int,
    dataset: str,
) -> Tuple[str, str | None]:
    """Save an upload locally and optionally mirror it to Google Drive."""
    safe_name = sanitize_audio_filename(audio_file.filename)
    validate_audio_content_type(audio_file.content_type)
    extension = Path(safe_name).suffix
    file_name = f"{id_audio}{extension}"
    storage_root = _configured_path(settings.STORAGE_PATH)
    storage_dir = storage_root / dataset
    local_file_path = storage_dir / file_name
    await copy_upload_to_path(
        audio_file,
        local_file_path,
        max_bytes=settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024,
    )
    drive_file_id = await save_to_gdrive(str(local_file_path), file_name)
    return str(local_file_path), drive_file_id
