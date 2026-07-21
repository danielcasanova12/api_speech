import io
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

import musics_router
import recordings_router
import storage
from main import app
from musics_router import _music_list_response, _upload_music_file, _validate_music_values
from recordings_router import _parse_extra_info, _validate_recording_metadata
from storage import S3ObjectAccess, _s3_object_key, get_s3_object_access
from upload_utils import (
    UploadTooLargeError,
    UploadValidationError,
    copy_upload_to_path,
    sanitize_audio_filename,
    validate_audio_content_type,
)


def make_upload(content: bytes, filename: str = "audio.wav") -> UploadFile:
    return UploadFile(
        file=io.BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": "audio/wav"}),
    )


def test_sanitize_audio_filename_removes_both_path_styles():
    assert sanitize_audio_filename("../../../../app/main.wav") == "main.wav"
    assert sanitize_audio_filename(r"..\..\Windows\system32\voice.WAV") == "voice.wav"


@pytest.mark.parametrize("filename", [None, "", "payload.exe", "audio"])
def test_sanitize_audio_filename_rejects_invalid_names(filename):
    with pytest.raises(UploadValidationError):
        sanitize_audio_filename(filename)


def test_validate_audio_content_type_rejects_non_audio():
    with pytest.raises(UploadValidationError):
        validate_audio_content_type("application/x-msdownload")


@pytest.mark.asyncio
async def test_copy_upload_streams_and_never_overwrites(tmp_path):
    destination = tmp_path / "recording.wav"
    size = await copy_upload_to_path(make_upload(b"1234"), destination, max_bytes=4)
    assert size == 4
    assert destination.read_bytes() == b"1234"

    with pytest.raises(FileExistsError):
        await copy_upload_to_path(make_upload(b"new"), destination, max_bytes=4)
    assert destination.read_bytes() == b"1234"


@pytest.mark.asyncio
async def test_copy_upload_removes_partial_file_when_limit_is_exceeded(tmp_path):
    destination = tmp_path / "too-large.wav"
    with pytest.raises(UploadTooLargeError):
        await copy_upload_to_path(make_upload(b"12345"), destination, max_bytes=4)
    assert not destination.exists()


def test_extra_info_must_be_a_json_object():
    assert _parse_extra_info('{"device": "browser"}') == {"device": "browser"}
    with pytest.raises(HTTPException) as error:
        _parse_extra_info("[]")
    assert error.value.status_code == 400


@pytest.mark.parametrize(
    "kwargs",
    [
        {"duration": 0, "sample_rate": 16000, "room_tone_start": None, "room_tone_end": None},
        {"duration": 1, "sample_rate": 0, "room_tone_start": None, "room_tone_end": None},
        {"duration": 1, "sample_rate": 16000, "room_tone_start": 0.8, "room_tone_end": 0.2},
        {"duration": 1, "sample_rate": 16000, "room_tone_start": 0, "room_tone_end": 2},
    ],
)
def test_recording_metadata_rejects_invalid_ranges(kwargs):
    with pytest.raises(HTTPException) as error:
        _validate_recording_metadata(**kwargs)
    assert error.value.status_code == 422


def test_music_metadata_validates_bpm_and_accepts_documented_time_signature_text():
    with pytest.raises(HTTPException):
        _validate_music_values(bpm=0, time_signature=None)

    assert _validate_music_values(bpm=120, time_signature="string") == (120, "string")
    assert _validate_music_values(bpm=120, time_signature="  ") == (120, None)

    with pytest.raises(HTTPException):
        _validate_music_values(bpm=120, time_signature="x" * 51)


def test_create_music_accepts_swagger_multipart_payload(monkeypatch):
    class FakeMusicSession:
        def __init__(self):
            self.music = None
            self.committed = False

        def add(self, music):
            self.music = music

        async def flush(self):
            self.music.id = 42

        async def commit(self):
            self.committed = True

        async def rollback(self):
            raise AssertionError("The valid multipart request must not roll back")

    session = FakeMusicSession()

    async def override_database():
        yield session

    async def fake_upload(_upload, *, music_id, kind, temporary_paths):
        assert music_id == 42
        assert temporary_paths == []
        return f"music/42/{kind}.mp3"

    monkeypatch.setattr(musics_router, "_upload_music_file", fake_upload)
    app.dependency_overrides[musics_router.get_async_session] = override_database
    app.dependency_overrides[musics_router.current_superuser] = lambda: SimpleNamespace()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/musics",
                data={
                    "nome": "musica",
                    "genero": "sertanejo",
                    "texto": "Baby fala pra mim Que... gosta de mim Baby",
                    "bpm": "123",
                    "time_signature": "string",
                },
                files={
                    "vocal_audio_file": ("vocal.mp3", b"vocal", "audio/mpeg"),
                    "instrumental_audio_file": (
                        "instrumental.mp3",
                        b"instrumental",
                        "audio/mpeg",
                    ),
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json() == {
        "id": 42,
        "nome": "musica",
        "genero": "sertanejo",
        "bpm": 123,
        "time_signature": "string",
        "has_vocal_audio": True,
        "has_instrumental_audio": True,
        "vocal_audio_url": None,
        "instrumental_audio_url": None,
    }
    assert session.committed is True


def test_s3_reference_parser_accepts_key_and_configured_bucket_url():
    assert _s3_object_key("folder/audio.wav") == "folder/audio.wav"
    assert (
        _s3_object_key(
            "https://unit-test-bucket.s3.sa-east-1.amazonaws.com/folder/audio%20file.wav"
        )
        == "folder/audio file.wav"
    )
    assert _s3_object_key("https://other-bucket.s3.amazonaws.com/audio.wav") is None


@pytest.mark.asyncio
async def test_music_uploads_use_unique_server_generated_keys(tmp_path, monkeypatch):
    generated_keys = []

    async def fake_save_to_s3(file_path, object_key):
        assert tmp_path in type(tmp_path)(file_path).parents
        generated_keys.append(object_key)
        return f"https://example.test/{object_key}"

    monkeypatch.setattr(musics_router, "MUSIC_TEMP_DIR", tmp_path)
    monkeypatch.setattr(musics_router, "save_to_s3", fake_save_to_s3)
    temporary_paths = []
    first_key = await _upload_music_file(
        make_upload(b"first", "../../app/main.wav"),
        music_id=7,
        kind="vocal",
        temporary_paths=temporary_paths,
    )
    second_key = await _upload_music_file(
        make_upload(b"second", "../../app/main.wav"),
        music_id=7,
        kind="vocal",
        temporary_paths=temporary_paths,
    )
    try:
        assert first_key != second_key
        assert generated_keys == [first_key, second_key]
        assert all(".." not in key and "main" not in key for key in generated_keys)
    finally:
        for path in temporary_paths:
            path.unlink(missing_ok=True)


def test_music_routes_are_really_protected_in_openapi():
    schema = app.openapi()
    for path, method in (
        ("/api/v1/recordings", "get"),
        ("/api/v1/recordings/{recording_id}/details", "get"),
        ("/api/v1/recordings/{recording_id}/audio", "get"),
        ("/api/v1/sessions/recent", "get"),
        ("/api/v1/sessions/{session_id}/recordings", "get"),
        ("/api/v1/musics", "get"),
        ("/api/v1/musics", "post"),
        ("/api/v1/musics/{music_id}", "get"),
        ("/api/v1/musics/{music_id}/audio", "get"),
        ("/api/v1/musics/{music_id}", "patch"),
        ("/api/v1/musics/{music_id}", "delete"),
        ("/api/v1/recordings/sessions/{session_id}/audios", "get"),
    ):
        assert schema["paths"][path][method].get("security")


@pytest.mark.asyncio
async def test_s3_object_access_uses_head_and_presigns(monkeypatch):
    class FakeS3Client:
        def head_object(self, **kwargs):
            assert kwargs == {"Bucket": "unit-test-bucket", "Key": "folder/audio.wav"}
            return {"ContentType": "audio/wav", "ContentLength": 123}

        def generate_presigned_url(self, _operation, *, Params, ExpiresIn):
            assert Params == {"Bucket": "unit-test-bucket", "Key": "folder/audio.wav"}
            assert ExpiresIn == 900
            return "https://signed.example/audio.wav"

    monkeypatch.setattr(storage, "get_s3_client", lambda: FakeS3Client())

    access = await get_s3_object_access("folder/audio.wav", expiration=900)

    assert access.available is True
    assert access.url == "https://signed.example/audio.wav"
    assert access.content_type == "audio/wav"
    assert access.size_bytes == 123
    assert access.expires_in == 900


@pytest.mark.asyncio
async def test_recording_audio_response_marks_missing_audio_without_failing(monkeypatch):
    async def missing_access(_reference, _expiration):
        return S3ObjectAccess(available=False, missing=True)

    monkeypatch.setattr(recordings_router, "get_s3_object_access", missing_access)
    response = await recordings_router._recording_audio_response(
        SimpleNamespace(
            id_recordings=10,
            session_id=2,
            dataset_id=3,
            bloco_id=4,
            frase_id=None,
            duration=1.5,
            format="wav",
            sample_rate=16000,
            frase_content="texto",
            is_test=False,
            created_at="2026-07-11T10:30:00Z",
            audio_url_s3="missing.wav",
            path_local=None,
        )
    )

    assert response.audio_available is False
    assert response.audio_url is None


@pytest.mark.asyncio
async def test_music_list_only_presigns_when_requested(monkeypatch):
    calls = []

    async def fake_presign(reference, expiration=3600):
        calls.append((reference, expiration))
        return f"https://signed.example/{reference}"

    monkeypatch.setattr(musics_router, "get_s3_presigned_url", fake_presign)
    music = SimpleNamespace(
        id=7,
        nome="Song",
        genero="pop",
        bpm=120,
        time_signature="4/4",
        vocal_audio_filepath="vocal.wav",
        instrumental_audio_filepath="instrumental.wav",
    )

    without_urls = await _music_list_response(music)
    with_urls = await _music_list_response(music, include_audio_urls=True)

    assert without_urls.vocal_audio_url is None
    assert without_urls.instrumental_audio_url is None
    assert with_urls.vocal_audio_url == "https://signed.example/vocal.wav"
    assert with_urls.instrumental_audio_url == "https://signed.example/instrumental.wav"
    assert calls == [("vocal.wav", 900), ("instrumental.wav", 900)]
