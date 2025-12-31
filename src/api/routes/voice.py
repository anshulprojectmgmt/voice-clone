"""
Voice API Routes
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import List
import uuid
from datetime import datetime
from pathlib import Path
import shutil

from ..models.voice import (
    VoiceUploadResponse,
    VoiceLibraryResponse,
    VoiceLibraryItem,
)

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])

# Voice library storage (in production, use a database)
voice_library: List[VoiceLibraryItem] = []

# Voice samples directory
VOICE_SAMPLES_DIR = Path("src/output/voice_samples")
VOICE_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

# Default voice ID
DEFAULT_VOICE_ID = "default"


def get_default_voice_path() -> Path:
    """Get path to default voice sample"""
    # Try multiple paths for the default voice
    possible_paths = [
        Path(__file__).parents[3] / "samples" / "test_voice.wav",  # From src/api/routes/voice.py to project root
        Path("../samples/test_voice.wav"),  # Relative from src/ directory (Render)
        Path("samples/test_voice.wav"),  # Direct path
    ]

    for default_voice in possible_paths:
        if default_voice.exists():
            return default_voice

    # Fallback to first available voice sample if default doesn't exist
    voice_files = list(VOICE_SAMPLES_DIR.glob("*.wav"))
    if voice_files:
        return voice_files[0]
    return None


@router.post("/upload", response_model=VoiceUploadResponse)
async def upload_voice_sample(file: UploadFile = File(...)):
    """
    Upload a voice sample for voice cloning
    """
    try:
        # Validate file type
        allowed_extensions = {".wav", ".mp3", ".flac"}
        file_extension = Path(file.filename).suffix.lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}"
            )

        # Generate unique voice ID
        voice_id = str(uuid.uuid4())

        # Save file
        file_path = VOICE_SAMPLES_DIR / f"{voice_id}{file_extension}"

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Get audio duration and sample rate
        try:
            import librosa
            audio, sr = librosa.load(str(file_path), sr=None)
            duration = librosa.get_duration(y=audio, sr=sr)
            sample_rate = sr
        except Exception as e:
            # If librosa fails, use default values
            duration = 0.0
            sample_rate = 22050

        # Generate URL
        sample_url = f"/output/voice_samples/{voice_id}{file_extension}"

        # Add to voice library
        voice_item = VoiceLibraryItem(
            voice_id=voice_id,
            name=file.filename,
            uploaded_at=datetime.now().isoformat(),
            sample_url=sample_url,
            duration=duration,
        )
        voice_library.append(voice_item)

        return VoiceUploadResponse(
            voice_id=voice_id,
            sample_url=sample_url,
            duration=duration,
            sample_rate=sample_rate,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload voice sample: {str(e)}")


@router.get("/library", response_model=VoiceLibraryResponse)
async def get_voice_library():
    """
    Get list of all uploaded voice samples
    """
    try:
        return VoiceLibraryResponse(voices=voice_library)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get voice library: {str(e)}")


@router.get("/default", response_model=VoiceUploadResponse)
async def get_default_voice():
    """
    Get the default voice sample information
    """
    try:
        default_path = get_default_voice_path()
        if not default_path:
            raise HTTPException(
                status_code=404,
                detail="No default voice available. Please upload a voice sample first."
            )

        # Get audio duration
        try:
            import librosa
            audio, sr = librosa.load(str(default_path), sr=None)
            duration = librosa.get_duration(y=audio, sr=sr)
            sample_rate = sr
        except Exception:
            duration = 0.0
            sample_rate = 24000

        return VoiceUploadResponse(
            voice_id=DEFAULT_VOICE_ID,
            sample_url=f"/output/voice_samples/{default_path.name}",
            duration=duration,
            sample_rate=sample_rate,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get default voice: {str(e)}")


@router.delete("/{voice_id}")
async def delete_voice_sample(voice_id: str):
    """
    Delete a voice sample from the library
    """
    try:
        # Find voice in library
        voice_item = None
        for i, voice in enumerate(voice_library):
            if voice.voice_id == voice_id:
                voice_item = voice_library.pop(i)
                break

        if not voice_item:
            raise HTTPException(status_code=404, detail="Voice sample not found")

        # Delete file
        for file_path in VOICE_SAMPLES_DIR.glob(f"{voice_id}.*"):
            file_path.unlink()

        return {"message": "Voice sample deleted successfully", "voice_id": voice_id}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete voice sample: {str(e)}")
