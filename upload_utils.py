import re
from pathlib import Path

from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool


COPY_CHUNK_SIZE = 1024 * 1024

ALLOWED_AUDIO_EXTENSIONS = {
    ".aac",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".opus",
    ".wav",
    ".webm",
}

ALLOWED_AUDIO_CONTENT_TYPES = {
    "audio/aac",
    "audio/flac",
    "audio/m4a",
    "audio/mp4",
    "audio/mpeg",
    "audio/mp3",
    "audio/ogg",
    "audio/opus",
    "audio/vnd.wave",
    "audio/wav",
    "audio/webm",
    "audio/x-flac",
    "audio/x-m4a",
    "audio/x-wav",
}


class UploadValidationError(ValueError):
    """Raised when a client-provided upload is not acceptable."""


class UploadTooLargeError(UploadValidationError):
    """Raised when an upload exceeds the configured byte limit."""


def sanitize_audio_filename(filename: str | None) -> str:
    """Return a basename safe for logs and object-storage keys."""
    if not filename or not filename.strip():
        raise UploadValidationError("Audio filename is required.")

    # Browsers normally send a basename, but multipart clients may send either
    # POSIX or Windows paths. Normalize both before taking the final component.
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not basename or "\x00" in basename:
        raise UploadValidationError("Audio filename is invalid.")

    suffix = Path(basename).suffix.lower()
    if suffix not in ALLOWED_AUDIO_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_AUDIO_EXTENSIONS))
        raise UploadValidationError(
            f"Unsupported audio extension '{suffix or '<none>'}'. Allowed extensions: {allowed}."
        )

    stem = Path(basename).stem
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    if not safe_stem:
        safe_stem = "audio"

    return f"{safe_stem[:80]}{suffix}"


def validate_audio_content_type(content_type: str | None) -> None:
    if not content_type:
        raise UploadValidationError("Audio content type is required.")

    normalized = content_type.split(";", 1)[0].strip().lower()
    if normalized not in ALLOWED_AUDIO_CONTENT_TYPES:
        raise UploadValidationError(f"Unsupported audio content type '{content_type}'.")


async def copy_upload_to_path(
    upload: UploadFile,
    destination: Path,
    *,
    max_bytes: int,
) -> int:
    """Copy an UploadFile without loading it all into memory.

    The destination is opened exclusively so an existing file is never
    overwritten. Partial files are removed if validation or I/O fails.
    """
    if max_bytes <= 0:
        raise ValueError("max_bytes must be greater than zero")

    destination.parent.mkdir(parents=True, exist_ok=True)
    created_destination = False

    def _copy() -> int:
        nonlocal created_destination
        total = 0
        upload.file.seek(0)
        with destination.open("xb") as output:
            created_destination = True
            while True:
                chunk = upload.file.read(COPY_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise UploadTooLargeError(
                        f"Audio file exceeds the {max_bytes // (1024 * 1024)} MB limit."
                    )
                output.write(chunk)

        if total == 0:
            raise UploadValidationError("Audio file is empty.")
        return total

    try:
        return await run_in_threadpool(_copy)
    except Exception:
        if created_destination:
            destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
