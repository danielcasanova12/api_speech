from fastapi import UploadFile, HTTPException, status
from pydub import AudioSegment
import io

# --- Constants ---
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_FORMATS = ["audio/webm", "audio/wav", "audio/mp3", "audio/ogg", "audio/opus"]
DURATION_TOLERANCE_SECONDS = 2.0  # Increased tolerance

def validate_form_data(form_data):
    """
    Validates the metadata from the form.
    Placeholder for database checks.
    """
    # In a real app, you would check if datasetId, phraseId, etc., exist in your DB.
    # For example:
    # if not Dataset.exists(form_data.datasetId):
    #     raise HTTPException(status_code=400, detail=f"Dataset with id {form_data.datasetId} not found.")
    # if not Phrase.exists(form_data.phraseId):
    #     raise HTTPException(status_code=400, detail=f"Phrase with id {form_data.phraseId} not found.")
    pass

async def is_valid_audio_file(file: UploadFile) -> bool:
    """
    Checks if the audio file is valid and not corrupted by trying to read it.
    """
    try:
        content = await file.read()
        await file.seek(0)  # Reset file pointer after reading

        if not content:
            return False

        # Use pydub to check the integrity
        audio = AudioSegment.from_file(io.BytesIO(content))

        # Check for basic properties
        if len(audio) == 0 or audio.frame_rate < 8000:
            return False
            
        return True
    except Exception:
        return False

async def get_audio_duration(file: UploadFile) -> float:
    """
    Calculates the duration of the audio file in seconds.
    """
    try:
        content = await file.read()
        await file.seek(0) # Reset file pointer

        audio = AudioSegment.from_file(io.BytesIO(content))
        return len(audio) / 1000.0  # pydub duration is in milliseconds
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not process audio file to get duration: {e}"
        )

async def validate_audio(file: UploadFile, claimed_duration: float | None):
    """
    Performs all validations on the uploaded audio file.
    """
    # 1. Validate file size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds the limit of {MAX_FILE_SIZE_MB}MB."
        )
    await file.seek(0)

    # 2. Validate MIME type
    if file.content_type not in ALLOWED_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported audio format: {file.content_type}. Supported formats are {', '.join(ALLOWED_FORMATS)}."
        )

    # 3. Validate audio integrity
    if not await is_valid_audio_file(file):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file appears to be corrupted or empty."
        )

    # 4. Validate duration if provided
    if claimed_duration is not None:
        actual_duration = await get_audio_duration(file)
        if abs(actual_duration - claimed_duration) > DURATION_TOLERANCE_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Claimed duration ({claimed_duration:.2f}s) does not match actual duration ({actual_duration:.2f}s) within tolerance."
            )
