import boto3
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from botocore.exceptions import ClientError
from pathlib import Path

from database import get_async_session
from models import Music
from schemas import MusicListResponse, MusicDetailResponse
from storage import get_s3_presigned_url, save_to_s3
from config import settings

router = APIRouter(prefix="/musics", tags=["musics"])

def get_s3_client():
    return boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION
    )

async def delete_s3_object(s3_key: str):
    """Deletes an object from S3 using its full key."""
    if not s3_key:
        return
    try:
        s3_client = get_s3_client()
        s3_client.delete_object(Bucket="ermis-datasets", Key=s3_key)
        print(f"Successfully deleted {s3_key} from S3.")
    except Exception as e:
        print(f"Error deleting old S3 object {s3_key}: {e}")

@router.post("", response_model=MusicListResponse, status_code=status.HTTP_201_CREATED)
async def create_music(
    nome: str = Form(...),
    genero: str = Form(...),
    texto: Optional[str] = Form(None),
    bpm: Optional[int] = Form(None),
    time_signature: Optional[str] = Form(None),
    vocal_audio_file: Optional[UploadFile] = File(None),
    instrumental_audio_file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_async_session)
):
    # Create the music record first to get the ID
    new_music = Music(nome=nome, genero=genero, texto=texto, bpm=bpm, time_signature=time_signature)
    db.add(new_music)
    await db.commit()
    await db.refresh(new_music)

    vocal_filepath = None
    instrumental_filepath = None

    import os
    os.makedirs("/tmp/musics", exist_ok=True)

    if vocal_audio_file:
        filename = vocal_audio_file.filename
        local_path = f"/tmp/musics/{new_music.id}_vocal_{filename}"
        with open(local_path, "wb") as f:
            content = await vocal_audio_file.read()
            f.write(content)

        s3_key = f"akcit_datasets/music/musics/{new_music.id}/vocal/{filename}"
        s3_url = await save_to_s3(local_path, s3_key)
        if s3_url:
            vocal_filepath = s3_key

        try:
            os.remove(local_path)
        except:
            pass

    if instrumental_audio_file:
        filename = instrumental_audio_file.filename
        local_path = f"/tmp/musics/{new_music.id}_instrumental_{filename}"
        with open(local_path, "wb") as f:
            content = await instrumental_audio_file.read()
            f.write(content)

        s3_key = f"akcit_datasets/music/musics/{new_music.id}/instrumental/{filename}"
        s3_url = await save_to_s3(local_path, s3_key)
        if s3_url:
            instrumental_filepath = s3_key

        try:
            os.remove(local_path)
        except:
            pass

    # Update DB with S3 filepaths if uploaded
    if vocal_filepath or instrumental_filepath:
        if vocal_filepath:
            new_music.vocal_audio_filepath = vocal_filepath
        if instrumental_filepath:
            new_music.instrumental_audio_filepath = instrumental_filepath
        await db.commit()
        await db.refresh(new_music)

    return MusicListResponse(
        id=new_music.id,
        nome=new_music.nome,
        genero=new_music.genero,
        bpm=new_music.bpm,
        time_signature=new_music.time_signature,
        has_vocal_audio=bool(new_music.vocal_audio_filepath),
        has_instrumental_audio=bool(new_music.instrumental_audio_filepath)
    )

@router.get("", response_model=List[MusicListResponse])
async def list_musics(
    genero: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session)
):
    stmt = select(Music)
    if genero:
        stmt = stmt.where(Music.genero == genero)

    result = await db.execute(stmt)
    musics = result.scalars().all()

    response = []
    for m in musics:
        response.append(MusicListResponse(
            id=m.id,
            nome=m.nome,
            genero=m.genero,
            bpm=m.bpm,
            time_signature=m.time_signature,
            has_vocal_audio=bool(m.vocal_audio_filepath),
            has_instrumental_audio=bool(m.instrumental_audio_filepath)
        ))
    return response

@router.get("/{music_id}", response_model=MusicDetailResponse)
async def get_music(music_id: int, db: AsyncSession = Depends(get_async_session)):
    stmt = select(Music).where(Music.id == music_id)
    result = await db.execute(stmt)
    music = result.scalars().first()

    if not music:
        raise HTTPException(status_code=404, detail="Music not found")

    vocal_url = None
    instrumental_url = None

    if music.vocal_audio_filepath:
        # Generate presigned URL. Note: get_s3_presigned_url uses URL, but here we only have key,
        # so we need to pass a fake URL or fix the function usage.
        # Actually, get_s3_presigned_url expects full url.
        # Note: bucket name is hardcoded in storage.py to "ermis-datasets"
        fake_vocal_url = f"https://ermis-datasets.s3.{settings.AWS_REGION}.amazonaws.com/{music.vocal_audio_filepath}"
        vocal_url = await get_s3_presigned_url(fake_vocal_url)

    if music.instrumental_audio_filepath:
        fake_instrumental_url = f"https://ermis-datasets.s3.{settings.AWS_REGION}.amazonaws.com/{music.instrumental_audio_filepath}"
        instrumental_url = await get_s3_presigned_url(fake_instrumental_url)

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
        has_instrumental_audio=bool(music.instrumental_audio_filepath)
    )

@router.patch("/{music_id}", response_model=MusicListResponse)
async def update_music(
    music_id: int,
    nome: Optional[str] = Form(None),
    genero: Optional[str] = Form(None),
    texto: Optional[str] = Form(None),
    bpm: Optional[int] = Form(None),
    time_signature: Optional[str] = Form(None),
    vocal_audio_file: Optional[UploadFile] = File(None),
    instrumental_audio_file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_async_session)
):
    stmt = select(Music).where(Music.id == music_id)
    result = await db.execute(stmt)
    music = result.scalars().first()

    if not music:
        raise HTTPException(status_code=404, detail="Music not found")

    if nome is not None:
        music.nome = nome
    if genero is not None:
        music.genero = genero
    if texto is not None:
        music.texto = texto
    if bpm is not None:
        music.bpm = bpm
    if time_signature is not None:
        music.time_signature = time_signature

    import os
    os.makedirs("/tmp/musics", exist_ok=True)

    if vocal_audio_file:
        filename = vocal_audio_file.filename
        local_path = f"/tmp/musics/{music.id}_vocal_{filename}"
        with open(local_path, "wb") as f:
            content = await vocal_audio_file.read()
            f.write(content)

        s3_key = f"akcit_datasets/music/musics/{music.id}/vocal/{filename}"
        s3_url = await save_to_s3(local_path, s3_key)
        if s3_url:
            # delete old one after successful upload
            if music.vocal_audio_filepath:
                await delete_s3_object(music.vocal_audio_filepath)
            music.vocal_audio_filepath = s3_key

        try:
            os.remove(local_path)
        except:
            pass

    if instrumental_audio_file:
        filename = instrumental_audio_file.filename
        local_path = f"/tmp/musics/{music.id}_instrumental_{filename}"
        with open(local_path, "wb") as f:
            content = await instrumental_audio_file.read()
            f.write(content)

        s3_key = f"akcit_datasets/music/musics/{music.id}/instrumental/{filename}"
        s3_url = await save_to_s3(local_path, s3_key)
        if s3_url:
            # delete old one after successful upload
            if music.instrumental_audio_filepath:
                await delete_s3_object(music.instrumental_audio_filepath)
            music.instrumental_audio_filepath = s3_key

        try:
            os.remove(local_path)
        except:
            pass

    await db.commit()
    await db.refresh(music)

    return MusicListResponse(
        id=music.id,
        nome=music.nome,
        genero=music.genero,
        bpm=music.bpm,
        time_signature=music.time_signature,
        has_vocal_audio=bool(music.vocal_audio_filepath),
        has_instrumental_audio=bool(music.instrumental_audio_filepath)
    )
