"""
Voice API Routes
- Upload voice samples
- Fetch default voice
- Fetch voice library
"""

import logging
import uuid
import shutil
from pathlib import Path
from fastapi import (
    APIRouter,
    HTTPException,
    UploadFile,
    File,
    Depends,
    Form,
    status,
)

from ...auth.dependencies import get_current_user, get_optional_user
from ...database import voice_service
from ..models.voice import (
    VoiceUploadResponse,
    VoiceLibraryResponse,
    VoiceLibraryItem,
)
from ...services.s3_service import upload_voice_to_s3

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/voice", tags=["voice"])

# --------------------------------------------------
# STORAGE LOCATION
# --------------------------------------------------
# LOCAL DEV: src/output/voice_samples
# RENDER PROD: mount persistent disk or change to /var/data/voice_samples
VOICE_DIR = Path("src/output/voice_samples")
VOICE_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".flac"}


# --------------------------------------------------
# UPLOAD VOICE
# --------------------------------------------------
@router.post(
    "/upload",
    response_model=VoiceUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_voice_sample(
    file: UploadFile = File(...),
    name: str = Form(...),
    is_default: bool = Form(False),
    user: dict = Depends(get_current_user),
):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid audio format")

    # 🔥 Upload directly to S3
    s3_url = upload_voice_to_s3(
        file.file,
        file.filename,
        file.content_type or "audio/wav",
    )

    # 🔥 Store ONLY S3 URL in DB
    voice = voice_service.create_voice_profile(
        user_id=user["id"],
        name=name,
        audio_file_path=s3_url,
        is_default=is_default,
    )

    if not voice:
        raise HTTPException(status_code=500, detail="Failed to save voice")

    return VoiceUploadResponse(
        voice_id=voice.voice_id,
        name=voice.name,
        sample_url=s3_url,  # ✅ S3 URL
        duration=voice.duration,
        sample_rate=voice.sample_rate,
        embeddings_cached=False,
        is_default=voice.is_default,
    )



# --------------------------------------------------
# GET DEFAULT VOICE  ✅ FIXES YOUR ERROR
# --------------------------------------------------
@router.get("/default", response_model=VoiceUploadResponse)
async def get_default_voice(user: dict = Depends(get_optional_user)):
    """
    Returns default voice
    - Logged in → user's default
    - Not logged in → system default (user_id = 1)
    """

    user_id = user["id"] if user else 1  # system fallback

    voice = voice_service.get_default_voice(user_id)
    if not voice:
        raise HTTPException(
            status_code=404,
            detail="No default voice available",
        )

    return VoiceUploadResponse(
        voice_id=voice.voice_id,
        name=voice.name,
        sample_url=voice.file_path,
        duration=voice.duration,
        sample_rate=voice.sample_rate,
        embeddings_cached=False,
        is_default=voice.is_default,
    )


# --------------------------------------------------
# VOICE LIBRARY (USER + SYSTEM)
# --------------------------------------------------
@router.get("/library", response_model=VoiceLibraryResponse)
async def get_voice_library(user: dict = Depends(get_optional_user)):
    """
    Returns all available voices
    - Logged in → user + system
    - Guest → system only
    """

    user_id = user["id"] if user else None
    voices = voice_service.get_voice_library(user_id)

    items = [
        VoiceLibraryItem(
            voice_id=v.voice_id,
            name=v.name,
            sample_url=v.file_path,
            duration=v.duration,
            sample_rate=v.sample_rate,
            is_default=v.is_default,
            embeddings_cached=False,
        )
        for v in voices
    ]

    return VoiceLibraryResponse(voices=items)

@router.delete("/{voice_id}")
async def delete_voice_sample(voice_id: str, user: dict = Depends(get_current_user)):
    """
    Delete a voice sample from the library

    Requires:
        - Authentication (Bearer token)
        - Voice must belong to authenticated user

    Args:
        voice_id: Voice ID to delete

    Returns:
        Success message
    """
    try:
        logger.info(f"Delete voice request: {voice_id} from user {user['username']}")

        # Delete voice profile (includes ownership check)
        success = voice_service.delete_voice_profile(voice_id, user["id"])

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Voice sample not found or access denied",
            )

        logger.info(f"✓ Voice deleted: {voice_id}")

        return {"message": "Voice sample deleted successfully", "voice_id": voice_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete voice sample: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete voice sample: {str(e)}",
        )

