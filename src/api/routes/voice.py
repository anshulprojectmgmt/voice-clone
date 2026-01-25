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

    voice_path = VOICE_DIR / f"{uuid.uuid4()}{ext}"

    with open(voice_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    voice = voice_service.create_voice_profile(
        user_id=user["id"],
        name=name,
        audio_file_path=str(voice_path),
        is_default=is_default,
    )

    if not voice:
        raise HTTPException(status_code=500, detail="Failed to save voice")

    return VoiceUploadResponse(
        voice_id=voice.voice_id,
        name=voice.name,
        sample_url=f"/output/voice_samples/{Path(voice.file_path).name}",
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
        sample_url=f"/output/voice_samples/{Path(voice.file_path).name}",
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
            sample_url=f"/output/voice_samples/{Path(v.file_path).name}",
            duration=v.duration,
            sample_rate=v.sample_rate,
            is_default=v.is_default,
            embeddings_cached=bool(v.embeddings_path),
        )
        for v in voices
    ]

    return VoiceLibraryResponse(voices=items)
