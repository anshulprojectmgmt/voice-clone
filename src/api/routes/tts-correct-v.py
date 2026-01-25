"""
TTS API Routes
Chatterbox TTS (TEXT + REFERENCE AUDIO)
STABLE FIX:
- No skipped sentences
- Natural pacing
- Proper WAV handling
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path
import uuid
import base64
import logging
import re
import io

import soundfile as sf
import numpy as np

from ...auth.dependencies import get_optional_user
from ...database.voice_service import get_voice_by_id, increment_usage
from ...story_narrator.runpod_client import RunPodTTSClient

router = APIRouter(prefix="/api/v1/tts", tags=["tts"])
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("src/output/audio")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE_RATE = 24000


# ============================
# MODELS
# ============================

class TTSGenerateRequest(BaseModel):
    voice_id: str
    text: str
    temperature: float = 0.6
    cfg_weight: float = 0.8


class TTSGenerateResponse(BaseModel):
    audio_url: str
    voice_id: str


# ============================
# TEXT PROCESSING
# ============================

def split_into_sentences(text: str) -> List[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def create_chunks(text: str, max_chars: int = 240) -> List[str]:
    sentences = split_into_sentences(text)
    chunks, current = [], ""

    for s in sentences:
        if len(current) + len(s) > max_chars:
            chunks.append(current)
            current = s
        else:
            current = f"{current} {s}" if current else s

    if current:
        chunks.append(current)

    return chunks


# ============================
# AUDIO HELPERS
# ============================

def decode_wav(audio_bytes: bytes) -> np.ndarray:
    data, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
    if sr != SAMPLE_RATE:
        raise RuntimeError(f"Sample rate mismatch: {sr}")
    if data.ndim > 1:
        data = data.mean(axis=1)
    return data


def generate_silence(seconds: float) -> np.ndarray:
    return np.zeros(int(seconds * SAMPLE_RATE), dtype=np.float32)


# ============================
# MAIN ENDPOINT
# ============================

@router.post("/generate", response_model=TTSGenerateResponse)
async def generate_tts(
    request: TTSGenerateRequest,
    user: Optional[dict] = Depends(get_optional_user),
):
    user_id = user["id"] if user else None

    voice = get_voice_by_id(request.voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found")

    if user_id and voice.user_id not in (user_id, 1):
        raise HTTPException(status_code=403, detail="Access denied")

    voice_path = Path(voice.file_path)
    if not voice_path.exists():
        raise HTTPException(status_code=500, detail="Voice audio missing")

    ref_audio_b64 = base64.b64encode(voice_path.read_bytes()).decode()

    chunks = create_chunks(request.text)
    logger.info(f"TTS chunks: {len(chunks)}")

    runpod = RunPodTTSClient()

    final_audio: List[np.ndarray] = []

    for idx, chunk in enumerate(chunks, 1):
        logger.info(f"Synth chunk {idx}/{len(chunks)}")

        audio_bytes = runpod.synthesize_with_reference_audio(
            text=chunk,
            ref_audio_b64=ref_audio_b64,
            temperature=request.temperature,
            cfg_weight=request.cfg_weight,
        )

        pcm = decode_wav(audio_bytes)
        final_audio.append(pcm)

        # sentence pause
        final_audio.append(generate_silence(0.35))

        # paragraph pause
        if idx % 4 == 0:
            final_audio.append(generate_silence(0.9))

    # ✅ CORRECT CONCATENATION
    full_pcm = np.concatenate(final_audio, axis=0)

    output_path = OUTPUT_DIR / f"{uuid.uuid4().hex}.wav"
    sf.write(output_path, full_pcm, SAMPLE_RATE, subtype="PCM_16")

    increment_usage(request.voice_id)

    return TTSGenerateResponse(
        audio_url=f"/output/audio/{output_path.name}",
        voice_id=request.voice_id,
    )
