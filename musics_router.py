import logging
import tempfile
import uuid
from pathlib import Path
from typing import List, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from auth_router import fastapi_users
from config import settings
from database import get_async_session
from models import Music, User
from schemas import MusicAudioAccessResponse, MusicDetailResponse, MusicListResponse
from storage import delete_from_s3, get_s3_object_access, get_s3_presigned_url, save_to_s3
from upload_utils import (
    UploadTooLargeError,
    UploadValidationError,
    copy_upload_to_path,
    sanitize_audio_filename,
    validate_audio_content_type,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/musics", tags=["musics"])
current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)
MUSIC_TEMP_DIR = Path(tempfile.gettempdir()) / "api_speech_musics"
DEFAULT_AUDIO_URL_EXPIRATION_SECONDS = 900


def _clean_required_text(value: str, field_name: str, max_length: int) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{field_name} must not be empty.",
        )
    if len(cleaned) > max_length:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{field_name} must contain at most {max_length} characters.",
        )
    return cleaned


def _validate_music_values(
    *,
    bpm: int | None,
    time_signature: str | None,
) -> tuple[int | None, str | None]:
    if bpm is not None and not 1 <= bpm <= 400:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="bpm must be between 1 and 400.",
        )
    if time_signature is not None:
        time_signature = time_signature.strip()
        if not time_signature:
            time_signature = None
        elif len(time_signature) > 50:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="time_signature must contain at most 50 characters.",
            )
    return bpm, time_signature


async def _stage_music_upload(
    upload: UploadFile,
    *,
    kind: str,
) -> tuple[Path, str]:
    try:
        safe_filename = sanitize_audio_filename(upload.filename)
        validate_audio_content_type(upload.content_type)
    except UploadValidationError as error:
        await upload.close()
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(error),
        ) from error

    suffix = Path(safe_filename).suffix
    temporary_path = MUSIC_TEMP_DIR / f"{uuid.uuid4().hex}_{kind}{suffix}"
    try:
        await copy_upload_to_path(
            upload,
            temporary_path,
            max_bytes=settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024,
        )
    except UploadTooLargeError as error:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(error),
        ) from error
    except UploadValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    return temporary_path, suffix


async def _upload_music_file(
    upload: UploadFile,
    *,
    music_id: int,
    kind: str,
    temporary_paths: list[Path],
) -> str | None:
    temporary_path, suffix = await _stage_music_upload(upload, kind=kind)
    temporary_paths.append(temporary_path)
    object_key = (
        f"akcit_datasets/music/musics/{music_id}/{kind}/"
        f"{uuid.uuid4().hex}{suffix}"
    )
    uploaded_url = await save_to_s3(str(temporary_path), object_key)
    if uploaded_url is None:
        logger.warning("Could not upload %s audio for music %s", kind, music_id)
        return None
    return object_key


async def _music_list_response(
    music: Music,
    *,
    include_audio_urls: bool = False,
) -> MusicListResponse:
    vocal_url = None
    instrumental_url = None
    if include_audio_urls and music.vocal_audio_filepath:
        vocal_url = await get_s3_presigned_url(
            music.vocal_audio_filepath,
            DEFAULT_AUDIO_URL_EXPIRATION_SECONDS,
        )
    if include_audio_urls and music.instrumental_audio_filepath:
        instrumental_url = await get_s3_presigned_url(
            music.instrumental_audio_filepath,
            DEFAULT_AUDIO_URL_EXPIRATION_SECONDS,
        )
    return MusicListResponse(
        id=music.id,
        nome=music.nome,
        genero=music.genero,
        bpm=music.bpm,
        time_signature=music.time_signature,
        has_vocal_audio=bool(music.vocal_audio_filepath),
        has_instrumental_audio=bool(music.instrumental_audio_filepath),
        vocal_audio_url=vocal_url,
        instrumental_audio_url=instrumental_url,
    )


@router.post("", response_model=MusicListResponse, status_code=status.HTTP_201_CREATED)
async def create_music(
    nome: str = Form(..., min_length=1, max_length=255),
    genero: str = Form(..., min_length=1, max_length=100),
    texto: str | None = Form(None),
    bpm: int | None = Form(None, ge=1, le=400),
    time_signature: str | None = Form(None, max_length=50),
    vocal_audio_file: UploadFile | None = File(None),
    instrumental_audio_file: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_superuser),
):
    del user  # Admin permission is enforced by the dependency.
    nome = _clean_required_text(nome, "nome", 255)
    genero = _clean_required_text(genero, "genero", 100)
    bpm, time_signature = _validate_music_values(
        bpm=bpm,
        time_signature=time_signature,
    )
    texto = texto.strip() if texto is not None else None

    temporary_paths: list[Path] = []
    uploaded_keys: list[str] = []
    try:
        music = Music(
            nome=nome,
            genero=genero,
            texto=texto,
            bpm=bpm,
            time_signature=time_signature,
        )
        db.add(music)
        await db.flush()

        if vocal_audio_file is not None:
            key = await _upload_music_file(
                vocal_audio_file,
                music_id=music.id,
                kind="vocal",
                temporary_paths=temporary_paths,
            )
            if key:
                music.vocal_audio_filepath = key
                uploaded_keys.append(key)

        if instrumental_audio_file is not None:
            key = await _upload_music_file(
                instrumental_audio_file,
                music_id=music.id,
                kind="instrumental",
                temporary_paths=temporary_paths,
            )
            if key:
                music.instrumental_audio_filepath = key
                uploaded_keys.append(key)

        response = await _music_list_response(music)
        await db.commit()
        return response
    except HTTPException:
        await db.rollback()
        for key in uploaded_keys:
            await delete_from_s3(key)
        raise
    except Exception as error:
        await db.rollback()
        for key in uploaded_keys:
            await delete_from_s3(key)
        logger.exception("Could not create music")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create music.",
        ) from error
    finally:
        for path in temporary_paths:
            path.unlink(missing_ok=True)


@router.get("", response_model=List[MusicListResponse])
async def list_musics(
    genero: str | None = None,
    include_audio_urls: bool = False,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    del user
    statement = select(Music)
    if genero:
        statement = statement.where(Music.genero == genero)
    result = await db.execute(statement.order_by(Music.id))
    return [
        await _music_list_response(music, include_audio_urls=include_audio_urls)
        for music in result.scalars().all()
    ]


@router.get("/{music_id}", response_model=MusicDetailResponse)
async def get_music(
    music_id: int,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    del user
    music = await db.get(Music, music_id)
    if not music:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Music not found")

    vocal_url = (
        await get_s3_presigned_url(
            music.vocal_audio_filepath,
            DEFAULT_AUDIO_URL_EXPIRATION_SECONDS,
        )
        if music.vocal_audio_filepath
        else None
    )
    instrumental_url = (
        await get_s3_presigned_url(
            music.instrumental_audio_filepath,
            DEFAULT_AUDIO_URL_EXPIRATION_SECONDS,
        )
        if music.instrumental_audio_filepath
        else None
    )
    return MusicDetailResponse(
        id=music.id,
        nome=music.nome,
        genero=music.genero,
        texto=music.texto,
        bpm=music.bpm,
        time_signature=music.time_signature,
        vocal_audio_url=vocal_url,
        instrumental_audio_url=instrumental_url,
        has_vocal_audio=bool(music.vocal_audio_filepath),
        has_instrumental_audio=bool(music.instrumental_audio_filepath),
    )


@router.patch("/{music_id}", response_model=MusicListResponse)
async def update_music(
    music_id: int,
    nome: str | None = Form(None),
    genero: str | None = Form(None),
    texto: str | None = Form(None),
    bpm: int | None = Form(None),
    time_signature: str | None = Form(None),
    vocal_audio_file: UploadFile | None = File(None),
    instrumental_audio_file: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_superuser),
):
    del user
    music = await db.get(Music, music_id)
    if not music:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Music not found")

    if nome is not None:
        music.nome = _clean_required_text(nome, "nome", 255)
    if genero is not None:
        music.genero = _clean_required_text(genero, "genero", 100)
    if texto is not None:
        music.texto = texto.strip()
    bpm, time_signature = _validate_music_values(
        bpm=bpm,
        time_signature=time_signature,
    )
    if bpm is not None:
        music.bpm = bpm
    if time_signature is not None:
        music.time_signature = time_signature

    temporary_paths: list[Path] = []
    uploaded_keys: list[str] = []
    old_keys_to_delete: list[str] = []
    try:
        if vocal_audio_file is not None:
            new_key = await _upload_music_file(
                vocal_audio_file,
                music_id=music.id,
                kind="vocal",
                temporary_paths=temporary_paths,
            )
            if new_key:
                if music.vocal_audio_filepath and music.vocal_audio_filepath != new_key:
                    old_keys_to_delete.append(music.vocal_audio_filepath)
                music.vocal_audio_filepath = new_key
                uploaded_keys.append(new_key)

        if instrumental_audio_file is not None:
            new_key = await _upload_music_file(
                instrumental_audio_file,
                music_id=music.id,
                kind="instrumental",
                temporary_paths=temporary_paths,
            )
            if new_key:
                if (
                    music.instrumental_audio_filepath
                    and music.instrumental_audio_filepath != new_key
                ):
                    old_keys_to_delete.append(music.instrumental_audio_filepath)
                music.instrumental_audio_filepath = new_key
                uploaded_keys.append(new_key)

        response = await _music_list_response(music)
        await db.commit()
    except HTTPException:
        await db.rollback()
        for key in uploaded_keys:
            await delete_from_s3(key)
        raise
    except Exception as error:
        await db.rollback()
        for key in uploaded_keys:
            await delete_from_s3(key)
        logger.exception("Could not update music %s", music_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update music.",
        ) from error
    finally:
        for path in temporary_paths:
            path.unlink(missing_ok=True)

    # Delete previous objects only after the new reference is durable.
    for old_key in old_keys_to_delete:
        await delete_from_s3(old_key)
    return response


@router.get("/{music_id}/audio", response_model=MusicAudioAccessResponse)
async def get_music_audio(
    music_id: int,
    kind: Literal["vocal", "instrumental"] = Query(...),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    del user
    music = await db.get(Music, music_id)
    if not music:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Music not found")

    reference = (
        music.vocal_audio_filepath
        if kind == "vocal"
        else music.instrumental_audio_filepath
    )
    access = await get_s3_object_access(
        reference,
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
            detail="Music audio file not found.",
        )
    return MusicAudioAccessResponse(
        music_id=music_id,
        kind=kind,
        audio_available=True,
        audio_url=access.url,
        expires_in=access.expires_in,
        mime_type=access.content_type,
        size_bytes=access.size_bytes,
    )


@router.delete("/{music_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_music(
    music_id: int,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_superuser),
):
    del user
    music = await db.get(Music, music_id)
    if not music:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Music not found")

    keys_to_delete = [
        key
        for key in (music.vocal_audio_filepath, music.instrumental_audio_filepath)
        if key
    ]
    try:
        await db.delete(music)
        await db.commit()
    except Exception as error:
        await db.rollback()
        logger.exception("Could not delete music %s", music_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete music.",
        ) from error

    for key in keys_to_delete:
        await delete_from_s3(key)
    return None
