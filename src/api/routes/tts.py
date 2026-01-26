"""
TTS API Routes — JOB BASED (PRODUCTION SAFE)
- Non-blocking
- Progress tracking
- AWS S3 compatible
- Render safe
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict
from pathlib import Path
import uuid
import base64
import logging
import re
import io
import requests

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

# --------------------------------------------------
# IN-MEMORY TASK STORE (Redis later)
# --------------------------------------------------
tasks: Dict[str, Dict] = {}

# ==================================================
# MODELS
# ==================================================

class TTSGenerateRequest(BaseModel):
    voice_id: str
    text: str
    temperature: float = 0.85
    cfg_weight: float = 0.2
    exaggeration: float = 0.3


class TTSGenerateResponse(BaseModel):
    task_id: str
    message: str


class TTSStatusResponse(BaseModel):
    status: str
    progress: int
    audio_url: Optional[str] = None
    error: Optional[str] = None


# ==================================================
# TEXT PROCESSING
# ==================================================

def split_into_sentences(text: str) -> List[str]:
    return [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", text.strip())
        if s.strip()
    ]


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


# ==================================================
# AUDIO HELPERS
# ==================================================

def load_voice_bytes(path_or_url: str) -> bytes:
    """
    Load voice audio from local disk OR S3 URL
    """
    if path_or_url.startswith("http"):
        resp = requests.get(path_or_url, timeout=30)
        resp.raise_for_status()
        return resp.content

    return Path(path_or_url).read_bytes()


def decode_wav(audio_bytes: bytes) -> np.ndarray:
    data, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
    if sr != SAMPLE_RATE:
        raise RuntimeError(f"Sample rate mismatch: {sr}")
    if data.ndim > 1:
        data = data.mean(axis=1)
    return data


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(seconds * SAMPLE_RATE), dtype=np.float32)


# ==================================================
# BACKGROUND JOB
# ==================================================

def run_tts_job(
    task_id: str,
    voice,
    text: str,
    temperature: float,
    cfg_weight: float,
    exaggeration: float,
):
    try:
        tasks[task_id]["status"] = "processing"
        tasks[task_id]["progress"] = 5

        # 🔥 Load reference voice (S3 or local)
        ref_audio_b64 = base64.b64encode(
            load_voice_bytes(voice.file_path)
        ).decode()

        chunks = create_chunks(text)
        total = len(chunks)
        logger.info(f"TTS chunks: {total}")

        runpod = RunPodTTSClient()
        audio_segments: List[np.ndarray] = []

        for i, chunk in enumerate(chunks, 1):
            logger.info(f"Synth chunk {i}/{total}")

            audio_bytes = runpod.synthesize_with_reference_audio(
                text=chunk,
                ref_audio_b64=ref_audio_b64,
                exaggeration=exaggeration,
                temperature=temperature,
                cfg_weight=cfg_weight,
            )

            audio_segments.append(decode_wav(audio_bytes))
            audio_segments.append(silence(0.35))

            tasks[task_id]["progress"] = int(5 + (85 * i / total))

        full_audio = np.concatenate(audio_segments, axis=0)

        output_path = OUTPUT_DIR / f"{task_id}.wav"
        sf.write(output_path, full_audio, SAMPLE_RATE, subtype="PCM_16")

        increment_usage(voice.voice_id)

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["audio_url"] = f"/output/audio/{output_path.name}"

    except Exception as e:
        logger.exception("TTS job failed")
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)


# ==================================================
# API ENDPOINTS
# ==================================================

@router.post("/generate", response_model=TTSGenerateResponse)
async def generate_tts(
    request: TTSGenerateRequest,
    background_tasks: BackgroundTasks,
    user: Optional[dict] = Depends(get_optional_user),
):
    user_id = user["id"] if user else None

    voice = get_voice_by_id(request.voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found")

    if user_id and voice.user_id not in (user_id, 1):
        raise HTTPException(status_code=403, detail="Access denied")

    task_id = str(uuid.uuid4())

    tasks[task_id] = {
        "status": "queued",
        "progress": 0,
    }

    background_tasks.add_task(
        run_tts_job,
        task_id,
        voice,
        request.text,
        request.temperature,
        request.cfg_weight,
        request.exaggeration,
    )

    return TTSGenerateResponse(
        task_id=task_id,
        message="Audio generation started",
    )


@router.get("/status/{task_id}", response_model=TTSStatusResponse)
async def get_tts_status(task_id: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TTSStatusResponse(**task)
