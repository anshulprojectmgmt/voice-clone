"""
Default Voice Initialization

Pre-caches the default voice on application startup to ensure zero latency
for first use. This is a key optimization that eliminates 400-1100ms overhead
on the first TTS request.
"""
import os
import logging
from pathlib import Path
from typing import Optional

from .voice_service import VoiceProfile

logger = logging.getLogger(__name__)

# System user ID for default voices
SYSTEM_USER_ID = int(os.getenv("SYSTEM_USER_ID", "1"))


def init_default_voice() -> Optional['VoiceProfile']:
    """
    Pre-cache default voice on application startup

    This function:
    1. Checks if default voice is already cached
    2. If not, locates the default voice sample file
    3. Initializes ChatterboxTTS model (skipped on low-memory environments)
    4. Computes and caches voice embeddings
    5. Stores in database

    Returns:
        VoiceProfile object if successful, None otherwise
    """
    from .voice_service import get_default_voice, create_voice_profile

    logger.info("Initializing default voice...")

    # Skip TTS model loading on production/Render free tier (512MB RAM limit)
    # Default voice will be lazy-loaded on first use instead
    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "production":
        logger.info("Production environment detected - skipping TTS model loading on startup")
        logger.info("Default voice will be created on first use to conserve memory")
        return None

    # Check if default voice is already cached
    existing = get_default_voice(SYSTEM_USER_ID)
    if existing:
        logger.info(f"Default voice already cached: {existing.voice_id}")
        logger.info(f"  - Name: {existing.name}")
        logger.info(f"  - File: {existing.file_path}")
        logger.info(f"  - Embeddings: {existing.embeddings_path}")
        return existing

    # Find default voice sample file
    default_voice_paths = [
        Path("samples/test_voice.wav"),
        Path("samples/REALTYAI.wav"),
        Path("src/output/voice_samples").glob("*.wav"),
    ]

    default_voice_path = None
    for path in default_voice_paths:
        if isinstance(path, Path) and path.exists():
            default_voice_path = path
            break
        elif hasattr(path, '__iter__'):  # It's a glob iterator
            try:
                default_voice_path = next(path)
                break
            except StopIteration:
                continue

    if not default_voice_path:
        logger.warning("No default voice sample found, skipping initialization")
        logger.warning("  Searched paths: samples/test_voice.wav, samples/REALTYAI.wav, src/output/voice_samples/*.wav")
        return None

    logger.info(f"Found default voice sample: {default_voice_path}")

    # Initialize ChatterboxTTS model
    try:
        logger.info("Loading ChatterboxTTS model for embeddings computation...")
        from chatterbox.tts import ChatterboxTTS

        # Use CPU for initialization to avoid GPU memory conflicts
        tts_model = ChatterboxTTS.from_pretrained(device="cpu")
        logger.info("ChatterboxTTS model loaded successfully")

    except Exception as e:
        logger.error(f"Failed to load ChatterboxTTS model: {e}")
        return None

    # Create voice profile with cached embeddings
    try:
        logger.info("Computing and caching default voice embeddings (this may take 400-1100ms)...")

        voice = create_voice_profile(
            user_id=SYSTEM_USER_ID,
            name="Default Voice",
            audio_file_path=str(default_voice_path),
            tts_model=tts_model,
            exaggeration=0.3,
            description="System default voice, pre-cached on startup",
            is_default=True
        )

        if voice:
            logger.info("✓ Default voice pre-cached successfully!")
            logger.info(f"  - Voice ID: {voice.voice_id}")
            logger.info(f"  - Embeddings: {voice.embeddings_path}")
            logger.info(f"  - Duration: {voice.duration:.1f}s")
            logger.info("  Future TTS requests will load from cache (<50ms) instead of recomputing")
        else:
            logger.error("Failed to create default voice profile")

        return voice

    except Exception as e:
        logger.error(f"Failed to pre-cache default voice: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def verify_default_voice() -> bool:
    """
    Verify that default voice is properly cached

    Returns:
        True if default voice exists and has cached embeddings, False otherwise
    """
    from .voice_service import get_default_voice

    voice = get_default_voice(SYSTEM_USER_ID)

    if not voice:
        logger.warning("No default voice found in database")
        return False

    if not voice.embeddings_path:
        logger.warning("Default voice has no cached embeddings path")
        return False

    embeddings_path = Path(voice.embeddings_path)
    if not embeddings_path.exists():
        logger.error(f"Default voice embeddings file not found: {embeddings_path}")
        return False

    logger.info("✓ Default voice verification successful")
    logger.info(f"  - Voice ID: {voice.voice_id}")
    logger.info(f"  - Embeddings: {voice.embeddings_path}")
    logger.info(f"  - File size: {embeddings_path.stat().st_size / 1024:.1f} KB")

    return True


if __name__ == "__main__":
    # For testing: run this script directly to initialize default voice
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("=" * 60)
    logger.info("Default Voice Initialization Script")
    logger.info("=" * 60)

    voice = init_default_voice()

    if voice:
        logger.info("\n" + "=" * 60)
        logger.info("SUCCESS: Default voice initialized")
        logger.info("=" * 60)
        verify_default_voice()
    else:
        logger.error("\n" + "=" * 60)
        logger.error("FAILED: Could not initialize default voice")
        logger.error("=" * 60)
