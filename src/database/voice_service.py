"""
Voice Service - Database operations for voice profiles with embeddings caching

This is the CORE OPTIMIZATION module that eliminates 400-1100ms overhead
by pre-computing and caching voice embeddings.
"""
import logging
import uuid
import shutil
import os
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from .connection import get_db, get_cursor, USE_POSTGRES
from .models import VoiceProfile

logger = logging.getLogger(__name__)

# Directories
VOICE_SAMPLES_DIR = Path("src/output/voice_samples")
VOICE_EMBEDDINGS_DIR = Path("src/output/voice_embeddings")

# Ensure directories exist
VOICE_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
VOICE_EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)

# Voice duration limits
MAX_VOICE_DURATION = 15.0  # seconds - prevents RunPod timeouts
MIN_VOICE_DURATION = 3.0   # seconds - minimum for quality cloning


def _format_query(query: str) -> str:
    """Convert SQL query placeholders for PostgreSQL compat if needed"""
    if USE_POSTGRES:
        return query.replace('?', '%s')
    return query


def crop_audio_to_limit(audio_path: str, max_duration: float = MAX_VOICE_DURATION) -> str:
    """
    Crop audio file to maximum duration to prevent RunPod timeouts.

    Only processes audio longer than max_duration. If audio is already short enough,
    returns the original path.

    Args:
        audio_path: Path to audio file
        max_duration: Maximum duration in seconds (default 15s)

    Returns:
        Path to processed audio file (may be same as input if no cropping needed)
    """
    import librosa
    import soundfile as sf

    # Load audio to check duration
    audio, sr = librosa.load(audio_path, sr=None)
    duration = len(audio) / sr

    logger.info(f"Original audio duration: {duration:.2f}s")

    # If already within limit, return original path
    if duration <= max_duration:
        logger.info(f"Audio duration ({duration:.2f}s) is within limit ({max_duration}s), no cropping needed")
        return audio_path

    # Crop to max duration
    logger.info(f"Cropping audio from {duration:.2f}s to {max_duration}s to prevent RunPod timeouts...")

    max_samples = int(max_duration * sr)
    cropped_audio = audio[:max_samples]

    # Save cropped audio
    cropped_path = str(Path(audio_path).with_stem(f"{Path(audio_path).stem}_cropped"))
    sf.write(cropped_path, cropped_audio, sr)

    logger.info(f"✓ Audio cropped and saved to: {cropped_path}")

    return cropped_path


def create_voice_profile_without_embeddings(
    user_id: int,
    name: str,
    audio_file_path: str,
    exaggeration: float = 0.3,
    description: Optional[str] = None,
    is_default: bool = False
) -> Optional[VoiceProfile]:
    """
    Create voice profile WITHOUT computing embeddings (memory-efficient for production)

    Embeddings will be computed lazily on first TTS request.
    This avoids memory spikes on Render/limited memory environments.

    Args:
        user_id: User who owns this voice
        name: Display name for voice
        audio_file_path: Path to source audio file
        exaggeration: Emotion exaggeration (0.0-1.0)
        description: Optional description
        is_default: Whether this is user's default voice

    Returns:
        VoiceProfile object if successful, None otherwise
    """
    try:
        voice_id = str(uuid.uuid4())

        # Process audio file (crop if needed)
        logger.info(f"Processing audio file: {audio_file_path}")
        processed_audio_path = crop_audio_to_limit(audio_file_path, MAX_VOICE_DURATION)

        # Get audio duration and sample rate
        import librosa
        audio, sr = librosa.load(processed_audio_path, sr=None)
        duration = len(audio) / sr

        # Validate minimum duration
        if duration < MIN_VOICE_DURATION:
            logger.error(f"Audio too short: {duration:.2f}s (minimum {MIN_VOICE_DURATION}s required)")
            raise ValueError(f"Voice sample must be at least {MIN_VOICE_DURATION} seconds long")

        # Copy processed audio to permanent location
        file_extension = Path(processed_audio_path).suffix
        new_file_path = VOICE_SAMPLES_DIR / f"{voice_id}{file_extension}"
        shutil.copy2(processed_audio_path, new_file_path)
        logger.info(f"Copied audio file to {new_file_path} (duration: {duration:.2f}s)")

        # Skip embeddings computation - will be done on first use
        logger.info(f"Skipping embeddings computation for '{name}' (will compute on first TTS request)")
        embeddings_path = None

        # If this is set as default, unset other defaults for this user
        if is_default:
            with get_db() as conn:
                cursor = get_cursor(conn)
                if USE_POSTGRES:
                    cursor.execute("""
                        UPDATE voice_profiles
                        SET is_default = FALSE
                        WHERE user_id = %s
                    """, (user_id,))
                else:
                    cursor.execute("""
                        UPDATE voice_profiles
                        SET is_default = 0
                        WHERE user_id = ?
                    """, (user_id,))
                conn.commit()

        # Insert into database (embeddings_path will be NULL)
        with get_db() as conn:
            cursor = get_cursor(conn)

            cursor.execute(_format_query("""
                INSERT INTO voice_profiles (
                    user_id, voice_id, name, description, file_path, embeddings_path,
                    sample_rate, duration, exaggeration, is_default
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """), (
                user_id, voice_id, name, description, str(new_file_path),
                embeddings_path,  # NULL - will be computed later
                int(sr), duration, exaggeration,
                1 if is_default else 0
            ))

            # Get the created voice profile
            voice_profile_id = cursor.lastrowid
            cursor.execute(_format_query("SELECT * FROM voice_profiles WHERE id = ?"), (voice_profile_id,))
            row = cursor.fetchone()

            conn.commit()

            if row:
                voice = VoiceProfile.from_db_row(row)
                logger.info(f"Created voice profile: {name} (id={voice.id}, voice_id={voice_id}, embeddings=lazy)")
                return voice

            return None
    except Exception as e:
        logger.error(f"Failed to create voice profile '{name}': {e}")
        # Cleanup on failure
        if 'new_file_path' in locals() and Path(new_file_path).exists():
            Path(new_file_path).unlink()
        return None


def create_voice_profile(
    user_id: int,
    name: str,
    audio_file_path: str,
    tts_model,  # ChatterboxTTS instance
    exaggeration: float = 0.3,
    description: Optional[str] = None,
    is_default: bool = False
) -> Optional[VoiceProfile]:
    """
    Create voice profile with pre-computed embeddings

    OPTIMIZATION: This method computes embeddings ONCE and caches to disk.
    Future TTS requests load from cache (<50ms) instead of recomputing (400-1100ms).

    Args:
        user_id: User who owns this voice
        name: Display name for voice
        audio_file_path: Path to source audio file
        tts_model: ChatterboxTTS model instance (for prepare_conditionals)
        exaggeration: Emotion exaggeration (0.0-1.0)
        description: Optional description
        is_default: Whether this is user's default voice

    Returns:
        VoiceProfile object if successful, None otherwise
    """
    try:
        voice_id = str(uuid.uuid4())

        # OPTIMIZATION: Crop audio to max 15 seconds to prevent RunPod timeouts
        logger.info(f"Processing audio file: {audio_file_path}")
        processed_audio_path = crop_audio_to_limit(audio_file_path, MAX_VOICE_DURATION)

        # Get audio duration and sample rate (from processed audio)
        import librosa
        audio, sr = librosa.load(processed_audio_path, sr=None)
        duration = len(audio) / sr

        # Validate minimum duration
        if duration < MIN_VOICE_DURATION:
            logger.error(f"Audio too short: {duration:.2f}s (minimum {MIN_VOICE_DURATION}s required)")
            raise ValueError(f"Voice sample must be at least {MIN_VOICE_DURATION} seconds long")

        # Copy processed audio to permanent location
        file_extension = Path(processed_audio_path).suffix
        new_file_path = VOICE_SAMPLES_DIR / f"{voice_id}{file_extension}"
        shutil.copy2(processed_audio_path, new_file_path)
        logger.info(f"Copied processed audio file to {new_file_path} (duration: {duration:.2f}s)")

        # OPTIMIZATION: Compute embeddings (400-1100ms overhead - only happens ONCE)
        logger.info(f"Computing embeddings for voice '{name}' (this may take 400-1100ms)...")
        start_time = datetime.now()

        tts_model.prepare_conditionals(str(new_file_path), exaggeration=exaggeration)

        # Save Conditionals to disk using existing save() method
        embeddings_filename = f"{voice_id}_exag{exaggeration:.2f}.pt"
        embeddings_path = VOICE_EMBEDDINGS_DIR / embeddings_filename
        tts_model.conds.save(embeddings_path)

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"✓ Embeddings computed and cached in {elapsed:.2f}s at: {embeddings_path}")

        # If this is set as default, unset other defaults for this user
        if is_default:
            with get_db() as conn:
                cursor = get_cursor(conn)
                if USE_POSTGRES:
                    cursor.execute("""
                        UPDATE voice_profiles
                        SET is_default = FALSE
                        WHERE user_id = %s
                    """, (user_id,))
                else:
                    cursor.execute("""
                        UPDATE voice_profiles
                        SET is_default = 0
                        WHERE user_id = ?
                    """, (user_id,))
                conn.commit()

        # Insert into database
        with get_db() as conn:
            cursor = get_cursor(conn)

            cursor.execute(_format_query("""
                INSERT INTO voice_profiles (
                    user_id, voice_id, name, description, file_path, embeddings_path,
                    sample_rate, duration, exaggeration, is_default
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """), (
                user_id, voice_id, name, description, str(new_file_path),
                str(embeddings_path), int(sr), duration, exaggeration,
                1 if is_default else 0
            ))

            # Get the created voice profile
            voice_profile_id = cursor.lastrowid
            cursor.execute(_format_query("SELECT * FROM voice_profiles WHERE id = ?"), (voice_profile_id,))
            row = cursor.fetchone()

            conn.commit()

            if row:
                voice = VoiceProfile.from_db_row(row)
                logger.info(f"Created voice profile: {name} (id={voice.id}, voice_id={voice_id})")
                return voice

            return None
    except Exception as e:
        logger.error(f"Failed to create voice profile '{name}': {e}")
        # Cleanup on failure
        if 'new_file_path' in locals() and Path(new_file_path).exists():
            Path(new_file_path).unlink()
        if 'embeddings_path' in locals() and Path(embeddings_path).exists():
            Path(embeddings_path).unlink()
        return None


def load_cached_embeddings(voice_id: str, exaggeration: float = 0.3):
    """
    Load cached embeddings from disk (FAST PATH <50ms)

    This is the OPTIMIZATION that avoids 400-1100ms prepare_conditionals() call.

    Args:
        voice_id: Voice ID
        exaggeration: Emotion exaggeration value

    Returns:
        Conditionals object if cached, None if cache miss
    """
    try:
        voice = get_voice_by_id(voice_id)
        if not voice:
            logger.warning(f"Voice {voice_id} not found")
            return None

        # Check if exaggeration matches (within tolerance)
        if abs(voice.exaggeration - exaggeration) > 0.01:
            logger.warning(f"Exaggeration mismatch: cached={voice.exaggeration:.2f}, requested={exaggeration:.2f}")
            return None

        # Check if embeddings file exists
        if not voice.embeddings_path:
            logger.warning(f"No embeddings path for voice {voice_id}")
            return None

        embeddings_path = Path(voice.embeddings_path)
        if not embeddings_path.exists():
            logger.error(f"Embeddings file not found: {embeddings_path}")
            return None

        # Load cached Conditionals using existing load() method
        logger.info(f"Loading cached embeddings from {embeddings_path}")
        start_time = datetime.now()

        # Import here to avoid circular dependency
        from chatterbox.tts import Conditionals
        conds = Conditionals.load(embeddings_path)

        elapsed = (datetime.now() - start_time).total_seconds() * 1000  # Convert to ms
        logger.info(f"✓ Cached embeddings loaded in {elapsed:.1f}ms (FAST PATH)")

        return conds
    except Exception as e:
        logger.error(f"Failed to load cached embeddings for {voice_id}: {e}")
        return None


def recache_embeddings(voice_id: str, tts_model, new_exaggeration: float) -> bool:
    """
    Recompute and cache embeddings with new exaggeration value

    Args:
        voice_id: Voice ID
        tts_model: ChatterboxTTS model instance
        new_exaggeration: New exaggeration value

    Returns:
        True if successful, False otherwise
    """
    try:
        voice = get_voice_by_id(voice_id)
        if not voice:
            return False

        logger.info(f"Recomputing embeddings for voice {voice_id} with exaggeration={new_exaggeration}")

        # Compute new embeddings
        tts_model.prepare_conditionals(voice.file_path, exaggeration=new_exaggeration)

        # Save new embeddings
        embeddings_filename = f"{voice_id}_exag{new_exaggeration:.2f}.pt"
        embeddings_path = VOICE_EMBEDDINGS_DIR / embeddings_filename
        tts_model.conds.save(embeddings_path)

        # Update database
        with get_db() as conn:
            cursor = get_cursor(conn)
            cursor.execute(_format_query("""
                UPDATE voice_profiles
                SET embeddings_path = ?, exaggeration = ?, updated_at = CURRENT_TIMESTAMP
                WHERE voice_id = ?
            """), (str(embeddings_path), new_exaggeration, voice_id))
            conn.commit()

        logger.info(f"✓ Embeddings recached for {voice_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to recache embeddings for {voice_id}: {e}")
        return False


def get_voice_by_id(voice_id: str) -> Optional[VoiceProfile]:
    """Get voice profile by voice_id"""
    try:
        with get_db() as conn:
            cursor = get_cursor(conn)
            cursor.execute(_format_query("SELECT * FROM voice_profiles WHERE voice_id = ?"), (voice_id,))
            row = cursor.fetchone()

            if row:
                return VoiceProfile.from_db_row(row)
            return None
    except Exception as e:
        logger.error(f"Failed to get voice {voice_id}: {e}")
        return None


def get_user_voices(user_id: int) -> List[VoiceProfile]:
    """Get all voice profiles for a user"""
    try:
        with get_db() as conn:
            cursor = get_cursor(conn)
            cursor.execute(_format_query("""
                SELECT * FROM voice_profiles
                WHERE user_id = ?
                ORDER BY created_at DESC
            """), (user_id,))
            rows = cursor.fetchall()

            return [VoiceProfile.from_db_row(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get voices for user {user_id}: {e}")
        return []


def get_default_voice(user_id: int) -> Optional[VoiceProfile]:
    """Get user's default voice profile"""
    try:
        with get_db() as conn:
            cursor = get_cursor(conn)
            if USE_POSTGRES:
                cursor.execute("""
                    SELECT * FROM voice_profiles
                    WHERE user_id = %s AND is_default = TRUE
                    LIMIT 1
                """, (user_id,))
            else:
                cursor.execute("""
                    SELECT * FROM voice_profiles
                    WHERE user_id = ? AND is_default = 1
                    LIMIT 1
                """, (user_id,))
            row = cursor.fetchone()

            if row:
                return VoiceProfile.from_db_row(row)
            return None
    except Exception as e:
        logger.error(f"Failed to get default voice for user {user_id}: {e}")
        return None


def set_default_voice(user_id: int, voice_id: str) -> bool:
    """Set a voice as user's default"""
    try:
        with get_db() as conn:
            cursor = get_cursor(conn)

            # Unset current default
            if USE_POSTGRES:
                cursor.execute("""
                    UPDATE voice_profiles
                    SET is_default = FALSE
                    WHERE user_id = %s
                """, (user_id,))

                # Set new default
                cursor.execute("""
                    UPDATE voice_profiles
                    SET is_default = TRUE
                    WHERE user_id = %s AND voice_id = %s
                """, (user_id, voice_id))
            else:
                cursor.execute("""
                    UPDATE voice_profiles
                    SET is_default = 0
                    WHERE user_id = ?
                """, (user_id,))

                # Set new default
                cursor.execute("""
                    UPDATE voice_profiles
                    SET is_default = 1
                    WHERE user_id = ? AND voice_id = ?
                """, (user_id, voice_id))

            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to set default voice for user {user_id}: {e}")
        return False


def delete_voice_profile(voice_id: str, user_id: int) -> bool:
    """
    Delete voice profile (with ownership check)

    Args:
        voice_id: Voice ID to delete
        user_id: User ID (for ownership verification)

    Returns:
        True if deleted, False otherwise
    """
    try:
        voice = get_voice_by_id(voice_id)
        if not voice or voice.user_id != user_id:
            logger.warning(f"Voice {voice_id} not found or access denied for user {user_id}")
            return False

        # Delete files
        if voice.file_path and Path(voice.file_path).exists():
            Path(voice.file_path).unlink()
        if voice.embeddings_path and Path(voice.embeddings_path).exists():
            Path(voice.embeddings_path).unlink()

        # Delete from database
        with get_db() as conn:
            cursor = get_cursor(conn)
            cursor.execute(_format_query("DELETE FROM voice_profiles WHERE voice_id = ?"), (voice_id,))
            conn.commit()

            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Deleted voice profile {voice_id}")
            return deleted
    except Exception as e:
        logger.error(f"Failed to delete voice {voice_id}: {e}")
        return False


def increment_usage(voice_id: str) -> bool:
    """Increment usage count and update last_used timestamp"""
    try:
        with get_db() as conn:
            cursor = get_cursor(conn)
            cursor.execute(_format_query("""
                UPDATE voice_profiles
                SET usage_count = usage_count + 1,
                    last_used = CURRENT_TIMESTAMP
                WHERE voice_id = ?
            """), (voice_id,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to increment usage for voice {voice_id}: {e}")
        return False


def get_voice_stats(voice_id: str) -> Optional[dict]:
    """Get usage statistics for a voice"""
    voice = get_voice_by_id(voice_id)
    if not voice:
        return None

    return {
        'voice_id': voice.voice_id,
        'name': voice.name,
        'usage_count': voice.usage_count,
        'last_used': voice.last_used,
        'created_at': voice.created_at,
        'duration': voice.duration,
        'is_default': voice.is_default
    }
