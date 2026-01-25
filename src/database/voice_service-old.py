"""
Voice Service - RunPod-native voice persistence layer
(PostgreSQL + SQLite compatible)
"""

import os
print("🔥 DB USED BY BACKEND:", os.getenv("DATABASE_URL"))

import json
import logging
import uuid
import shutil
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from .connection import get_db, get_cursor, USE_POSTGRES
from .models import VoiceProfile

logger = logging.getLogger(__name__)

VOICE_SAMPLES_DIR = Path("src/output/voice_samples")
VOICE_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

MAX_VOICE_DURATION = 15.0
MIN_VOICE_DURATION = 3.0


# --------------------------------------------------
# Helpers
# --------------------------------------------------
def normalize_audio(path: str):
    import librosa
    import soundfile as sf
    import numpy as np

    audio, sr = librosa.load(path, sr=48000, mono=True)

    # Trim silence
    audio, _ = librosa.effects.trim(audio, top_db=30)

    # Normalize amplitude
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak

    sf.write(path, audio, sr)
def _format_query(query: str) -> str:
    return query.replace("?", "%s") if USE_POSTGRES else query


# --------------------------------------------------
# Audio utilities
# --------------------------------------------------

def crop_audio_to_limit(audio_path: str, max_duration: float = MAX_VOICE_DURATION) -> str:
    import librosa
    import soundfile as sf

    audio, sr = librosa.load(audio_path, sr=None)
    duration = len(audio) / sr

    if duration <= max_duration:
        return audio_path

    cropped_audio = audio[: int(max_duration * sr)]
    cropped_path = str(Path(audio_path).with_stem(f"{Path(audio_path).stem}_cropped"))
    sf.write(cropped_path, cropped_audio, sr)

    return cropped_path


# --------------------------------------------------
# CORE FUNCTIONS
# --------------------------------------------------

def create_voice_profile(
    user_id: int,
    name: str,
    audio_file_path: str,
    speaker_embedding: List[float],
    exaggeration: float = 0.3,
    description: Optional[str] = None,
    is_default: bool = False,
) -> Optional[VoiceProfile]:

    try:
        voice_id = str(uuid.uuid4())

        processed_audio_path = crop_audio_to_limit(audio_file_path)
        normalize_audio(processed_audio_path)

        import librosa
        audio, sr = librosa.load(processed_audio_path, sr=None)
        duration = len(audio) / sr

        if duration < MIN_VOICE_DURATION:
            raise ValueError("Voice sample too short")

        new_file_path = VOICE_SAMPLES_DIR / f"{voice_id}{Path(processed_audio_path).suffix}"
        shutil.copy2(processed_audio_path, new_file_path)

        with get_db() as conn:
            cursor = get_cursor(conn)

            # Clear existing default if needed
            if is_default:
                cursor.execute(
                    _format_query(
                        "UPDATE voice_profiles SET is_default = FALSE WHERE user_id = ?"
                    ),
                    (user_id,),
                )

            cursor.execute(
                _format_query("""
                    INSERT INTO voice_profiles (
                        user_id, voice_id, name, description,
                        file_path, speaker_embedding,
                        sample_rate, duration, exaggeration, is_default
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """),
                (
                    user_id,
                    voice_id,
                    name,
                    description,
                    str(new_file_path),
                    json.dumps(speaker_embedding),
                    int(sr),
                    duration,
                    exaggeration,
                    is_default,
                ),
            )

            cursor.execute(
                _format_query("SELECT * FROM voice_profiles WHERE voice_id = ?"),
                (voice_id,),
            )
            row = cursor.fetchone()
            conn.commit()

            return VoiceProfile.from_db_row(row) if row else None

    except Exception as e:
        logger.error(f"Failed to create voice profile: {e}")
        return None


# --------------------------------------------------
# Retrieval
# --------------------------------------------------

def get_speaker_embedding(voice_id: str):
    with get_db() as conn:
        cursor = get_cursor(conn)
        cursor.execute(
            _format_query(
                "SELECT speaker_embedding FROM voice_profiles WHERE voice_id = ?"
            ),
            (voice_id,),
        )
        row = cursor.fetchone()

        if not row or not row["speaker_embedding"]:
            return None

        return json.loads(row["speaker_embedding"])


def get_voice_by_id(voice_id: str) -> Optional[VoiceProfile]:
    with get_db() as conn:
        cursor = get_cursor(conn)
        cursor.execute(
            _format_query("SELECT * FROM voice_profiles WHERE voice_id = ?"),
            (voice_id,),
        )
        row = cursor.fetchone()
        return VoiceProfile.from_db_row(row) if row else None


def get_user_voices(user_id: int) -> List[VoiceProfile]:
    with get_db() as conn:
        cursor = get_cursor(conn)
        cursor.execute(
            _format_query("SELECT * FROM voice_profiles WHERE user_id = ?"),
            (user_id,),
        )
        rows = cursor.fetchall()
        return [VoiceProfile.from_db_row(r) for r in rows]


# --------------------------------------------------
# Defaults
# --------------------------------------------------

def get_default_voice(user_id: int) -> Optional[VoiceProfile]:
    with get_db() as conn:
        cursor = get_cursor(conn)

        # 1️⃣ User default
        cursor.execute(
            _format_query("""
                SELECT *
                FROM voice_profiles
                WHERE user_id = ? AND is_default = TRUE
                LIMIT 1
            """),
            (user_id,),
        )
        row = cursor.fetchone()
        if row:
            return VoiceProfile.from_db_row(row)

        # 2️⃣ System fallback
        cursor.execute(
            _format_query("""
                SELECT *
                FROM voice_profiles
                WHERE user_id = 1 AND is_default = TRUE
                ORDER BY created_at DESC
                LIMIT 1
            """),
        )
        row = cursor.fetchone()
        return VoiceProfile.from_db_row(row) if row else None


def set_default_voice(user_id: int, voice_id: str) -> bool:
    with get_db() as conn:
        cursor = get_cursor(conn)

        cursor.execute(
            _format_query(
                "UPDATE voice_profiles SET is_default = FALSE WHERE user_id = ?"
            ),
            (user_id,),
        )

        cursor.execute(
            _format_query("""
                UPDATE voice_profiles
                SET is_default = TRUE
                WHERE voice_id = ? AND user_id = ?
            """),
            (voice_id, user_id),
        )

        conn.commit()
        return cursor.rowcount > 0


# --------------------------------------------------
# Stats / Delete
# --------------------------------------------------

def increment_usage(voice_id: str) -> None:
    with get_db() as conn:
        cursor = get_cursor(conn)
        cursor.execute(
            _format_query("""
                UPDATE voice_profiles
                SET usage_count = usage_count + 1,
                    last_used = CURRENT_TIMESTAMP
                WHERE voice_id = ?
            """),
            (voice_id,),
        )
        conn.commit()


def get_voice_stats(voice_id: str) -> Optional[dict]:
    with get_db() as conn:
        cursor = get_cursor(conn)
        cursor.execute(
            _format_query("""
                SELECT usage_count, last_used, created_at
                FROM voice_profiles
                WHERE voice_id = ?
            """),
            (voice_id,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        return {
            "usage_count": row["usage_count"],
            "last_used": row["last_used"],
            "created_at": row["created_at"],
        }


def delete_voice_profile(voice_id: str, user_id: int) -> bool:
    with get_db() as conn:
        cursor = get_cursor(conn)
        cursor.execute(
            _format_query("""
                DELETE FROM voice_profiles
                WHERE voice_id = ? AND user_id = ?
            """),
            (voice_id, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0
