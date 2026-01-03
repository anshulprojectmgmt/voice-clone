"""
Voice API Routes - WITH AUTHENTICATION & EMBEDDINGS CACHING

This is a critical optimization module that:
1. Requires authentication for voice uploads
2. Pre-computes and caches voice embeddings on upload (400-1100ms overhead)
3. Future TTS requests load from cache (<50ms) instead of recomputing
"""
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Form, status
from typing import List, Optional
import uuid
from datetime import datetime
from pathlib import Path
import shutil
import os

from ..models.voice import (
    VoiceUploadResponse,
    VoiceLibraryResponse,
    VoiceLibraryItem,
)
from ...auth.dependencies import get_current_user, get_optional_user
from ...database import voice_service
from ...database.voice_service import VOICE_SAMPLES_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])

# System user ID for default voices
SYSTEM_USER_ID = int(os.getenv("SYSTEM_USER_ID", "1"))

# Global TTS model for embeddings computation (initialized once)
_tts_model = None


def get_tts_model():
    """
    Get or initialize ChatterboxTTS model for embeddings computation

    This model is used ONLY for pre-computing voice embeddings on upload.
    It's loaded once and reused for all uploads to save memory.
    """
    global _tts_model

    if _tts_model is None:
        logger.info("Loading ChatterboxTTS model for voice embeddings computation...")
        from chatterbox.tts import ChatterboxTTS

        # Use CPU to avoid GPU memory conflicts with main TTS synthesis
        _tts_model = ChatterboxTTS.from_pretrained(device="cpu")
        logger.info("✓ ChatterboxTTS model loaded for embeddings")

    return _tts_model


@router.post("/upload", response_model=VoiceUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_voice_sample(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    exaggeration: float = Form(0.3),
    is_default: bool = Form(False),
    user: dict = Depends(get_current_user),  # REQUIRE AUTHENTICATION
):
    """
    Upload a voice sample with automatic embeddings caching

    **OPTIMIZATION**: This endpoint pre-computes voice embeddings and caches them to disk.
    Future TTS requests will load from cache (<50ms) instead of recomputing (400-1100ms).

    Requires:
        - Authentication (Bearer token)

    Args:
        - file: Audio file (.wav, .mp3, .flac)
        - name: Voice name (optional, defaults to filename)
        - description: Voice description (optional)
        - exaggeration: Emotion exaggeration (0.0-1.0, default 0.3)
        - is_default: Set as user's default voice (default false)

    Returns:
        Voice upload response with embeddings_cached=True
    """
    logger.info(f"Voice upload request from user: {user['username']}")

    try:
        # Validate file type
        allowed_extensions = {".wav", ".mp3", ".flac"}
        file_extension = Path(file.filename).suffix.lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}",
            )

        # Use filename as name if not provided
        voice_name = name if name else Path(file.filename).stem

        # Save to temporary location
        temp_path = Path(f"/tmp/{uuid.uuid4()}{file_extension}")
        try:
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            logger.info(f"Voice file saved to temp: {temp_path}")

            # Get TTS model for embeddings computation
            tts_model = get_tts_model()

            # Create voice profile with cached embeddings
            # THIS IS THE CRITICAL OPTIMIZATION: Pre-compute embeddings ONCE
            logger.info(f"Creating voice profile for '{voice_name}' (will cache embeddings)...")

            voice = voice_service.create_voice_profile(
                user_id=user["id"],
                name=voice_name,
                audio_file_path=str(temp_path),
                tts_model=tts_model,
                exaggeration=exaggeration,
                description=description,
                is_default=is_default,
            )

            if not voice:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create voice profile",
                )

            logger.info(f"✓ Voice profile created: {voice.voice_id}")
            logger.info(f"  - Embeddings cached at: {voice.embeddings_path}")
            logger.info(f"  - Future TTS requests will load from cache (<50ms)")

            return VoiceUploadResponse(
                voice_id=voice.voice_id,
                name=voice.name,
                sample_url=f"/output/voice_samples/{Path(voice.file_path).name}",
                duration=voice.duration,
                sample_rate=voice.sample_rate,
                embeddings_cached=True,  # NEW: Indicates embeddings are pre-computed
                is_default=voice.is_default,
            )

        finally:
            # Cleanup temp file
            if temp_path.exists():
                temp_path.unlink()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload voice sample: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload voice sample: {str(e)}",
        )


@router.get("/library", response_model=VoiceLibraryResponse)
async def get_voice_library(user: dict = Depends(get_current_user)):
    """
    Get list of user's uploaded voice samples

    Requires:
        - Authentication (Bearer token)

    Returns:
        List of voice profiles for the authenticated user
    """
    try:
        logger.debug(f"Get voice library request from user: {user['username']}")

        # Get user's voices from database
        voices = voice_service.get_user_voices(user["id"])

        # Convert to API response format
        voice_items = [
            VoiceLibraryItem(
                voice_id=voice.voice_id,
                name=voice.name,
                uploaded_at=voice.created_at,
                sample_url=f"/output/voice_samples/{Path(voice.file_path).name}",
                duration=voice.duration,
            )
            for voice in voices
        ]

        logger.debug(f"Returning {len(voice_items)} voices for user {user['username']}")

        return VoiceLibraryResponse(voices=voice_items)

    except Exception as e:
        logger.error(f"Failed to get voice library: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get voice library: {str(e)}",
        )


@router.get("/default", response_model=VoiceUploadResponse)
async def get_default_voice(user: Optional[dict] = Depends(get_optional_user)):
    """
    Get the default voice sample information

    Optional authentication:
        - If authenticated: returns user's default voice (or system default if none)
        - If not authenticated: returns system default voice

    Returns:
        Default voice information with embeddings_cached=True
    """
    try:
        user_id = user["id"] if user else SYSTEM_USER_ID

        logger.debug(f"Get default voice request (user_id={user_id})")

        # Get default voice from database
        voice = voice_service.get_default_voice(user_id)

        if not voice:
            logger.warning(f"No default voice found for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No default voice available. Please upload a voice sample first.",
            )

        logger.debug(f"Returning default voice: {voice.voice_id}")

        return VoiceUploadResponse(
            voice_id=voice.voice_id,
            name=voice.name,
            sample_url=f"/output/voice_samples/{Path(voice.file_path).name}",
            duration=voice.duration,
            sample_rate=voice.sample_rate,
            embeddings_cached=bool(voice.embeddings_path),
            is_default=voice.is_default,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get default voice: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get default voice: {str(e)}",
        )


@router.post("/set-default/{voice_id}")
async def set_default_voice(voice_id: str, user: dict = Depends(get_current_user)):
    """
    Set a voice as user's default

    Requires:
        - Authentication (Bearer token)

    Args:
        voice_id: Voice ID to set as default

    Returns:
        Success message
    """
    try:
        logger.info(f"Set default voice request: {voice_id} for user {user['username']}")

        # Verify voice ownership
        voice = voice_service.get_voice_by_id(voice_id)
        if not voice or voice.user_id != user["id"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Voice not found or access denied",
            )

        # Set as default
        success = voice_service.set_default_voice(user["id"], voice_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to set default voice",
            )

        logger.info(f"✓ Default voice set: {voice_id} for user {user['username']}")

        return {"message": "Default voice updated successfully", "voice_id": voice_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set default voice: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set default voice: {str(e)}",
        )


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


@router.get("/{voice_id}/stats")
async def get_voice_stats(voice_id: str, user: dict = Depends(get_current_user)):
    """
    Get usage statistics for a voice

    Requires:
        - Authentication (Bearer token)
        - Voice must belong to authenticated user

    Args:
        voice_id: Voice ID

    Returns:
        Voice usage statistics
    """
    try:
        # Verify ownership
        voice = voice_service.get_voice_by_id(voice_id)
        if not voice or voice.user_id != user["id"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Voice not found or access denied",
            )

        stats = voice_service.get_voice_stats(voice_id)

        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Voice statistics not found",
            )

        return stats

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get voice stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get voice stats: {str(e)}",
        )
