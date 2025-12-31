"""
TTS API Routes
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict
import uuid
import asyncio
from datetime import datetime
import base64
import os
from pathlib import Path
import re
import logging

from ..models.tts import (
    TTSGenerateRequest,
    TTSGenerateResponse,
    TTSStatusResponse,
)
from story_narrator.text_processor import TextProcessor

# AudioSynthesizer requires torch - make it optional
try:
    from story_narrator.audio_synthesizer import AudioSynthesizer
    _has_audio_synthesizer = True
except ImportError:
    _has_audio_synthesizer = False
    AudioSynthesizer = None

# RunPodTTSClient doesn't require torch - use as fallback
try:
    from story_narrator.runpod_client import RunPodTTSClient
    _has_runpod_client = True
except ImportError:
    _has_runpod_client = False
    RunPodTTSClient = None

# Set up logger
logger = logging.getLogger(__name__)

# Initialize text processor (same as Gradio)
text_processor = TextProcessor(
    max_chunk_length=500,  # 500 chars per chunk (not words!)
    paragraph_pause=1.0,   # 1 second pause between paragraphs
    sentence_pause=0.3     # 0.3 second pause between sentences
)

router = APIRouter(prefix="/api/v1/tts", tags=["tts"])

# Task storage (in production, use Redis or a database)
tasks: Dict[str, Dict] = {}

# Initialize synthesizer (could be AudioSynthesizer or RunPodTTSClient)
synthesizer = None

def get_synthesizer():
    """Get TTS synthesizer - uses RunPodTTSClient if torch is not available"""
    global synthesizer

    if synthesizer is None:
        # Prefer RunPodTTSClient if available (doesn't need torch)
        if _has_runpod_client:
            try:
                logger.info("Initializing RunPodTTSClient for TTS (torch not required)")
                synthesizer = RunPodTTSClient()
                logger.info("RunPodTTSClient initialized successfully")
            except ValueError as e:
                logger.error(f"Failed to initialize RunPodTTSClient: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"RunPod configuration error: {str(e)}. Please set RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID environment variables."
                )
        elif _has_audio_synthesizer:
            logger.info("Using AudioSynthesizer with RunPod")
            synthesizer = AudioSynthesizer(
                device="cpu",
                use_runpod=True
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="No TTS synthesizer available. Install torch for AudioSynthesizer or configure RunPod for RunPodTTSClient."
            )

    return synthesizer


def sanitize_text_for_tts(text: str) -> str:
    """
    Sanitize text to make it more suitable for TTS synthesis.
    Removes special characters and formatting that might confuse the model.
    """
    # Replace smart quotes with regular quotes
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace(''', "'").replace(''', "'")

    # Replace em dashes and en dashes with regular hyphens
    text = text.replace('—', '-').replace('–', '-')

    # Replace ellipsis with three periods
    text = text.replace('…', '...')

    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)

    # Remove any remaining non-ASCII characters that might cause issues
    # But keep common punctuation
    text = re.sub(r'[^\x00-\x7F]+', '', text)

    return text.strip()


def convert_to_mono(audio_path: Path) -> Path:
    """
    Convert audio file to mono and resample to 24kHz (Chatterbox TTS requirement).
    Returns path to processed audio file.
    """
    import librosa
    import soundfile as sf
    import numpy as np

    # Read audio file and resample to 24kHz
    target_sr = 24000  # Chatterbox TTS expects 24kHz
    audio, sr = sf.read(str(audio_path))

    # Convert to mono if stereo (2 channels)
    if len(audio.shape) > 1 and audio.shape[1] == 2:
        audio = np.mean(audio, axis=1)

    # Resample to target sample rate if needed
    if sr != target_sr:
        audio = librosa.resample(audio, orig_sr=sr, target_sr=target_sr)

    # Save processed audio
    processed_path = audio_path.with_stem(f"{audio_path.stem}_processed")
    sf.write(str(processed_path), audio, target_sr)
    return processed_path


async def generate_audio_task(task_id: str, request: TTSGenerateRequest):
    """
    Background task to generate audio
    """
    try:
        tasks[task_id]["status"] = "processing"
        tasks[task_id]["progress"] = 10

        synth = get_synthesizer()

        # Get voice sample path from voice ID or base64
        voice_sample_path = None
        voice_samples_dir = Path("src/output/voice_samples")

        if request.voiceSample:
            # Check if it's the default voice
            if request.voiceSample == "default":
                # Use the first available voice sample as default
                voice_files = list(voice_samples_dir.glob("*.wav"))
                if voice_files:
                    voice_sample_path = voice_files[0]
                    tasks[task_id]["progress"] = 20
                else:
                    tasks[task_id]["status"] = "failed"
                    tasks[task_id]["error"] = "No voice samples available. Please upload a voice sample first."
                    return
            # Check if it's a voice ID (UUID format) or base64 data
            elif len(request.voiceSample) < 100:  # Likely a voice ID
                # Look up the voice file from voice samples directory
                voice_files = list(voice_samples_dir.glob(f"{request.voiceSample}.*"))
                if voice_files:
                    voice_sample_path = voice_files[0]
                    tasks[task_id]["progress"] = 20
                else:
                    tasks[task_id]["status"] = "failed"
                    tasks[task_id]["error"] = f"Voice sample not found: {request.voiceSample}"
                    return
            else:
                # It's base64 encoded data
                try:
                    voice_data = base64.b64decode(request.voiceSample)
                    voice_sample_path = Path("src/output") / f"voice_sample_{task_id}.wav"
                    voice_sample_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(voice_sample_path, "wb") as f:
                        f.write(voice_data)
                    tasks[task_id]["progress"] = 20
                except Exception as e:
                    tasks[task_id]["status"] = "failed"
                    tasks[task_id]["error"] = f"Failed to decode voice sample: {str(e)}"
                    return

        # If no voice sample provided, use default
        if not voice_sample_path:
            voice_files = list(voice_samples_dir.glob("*.wav"))
            if voice_files:
                voice_sample_path = voice_files[0]
            else:
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["error"] = "No voice samples available. Please upload a voice sample first."
                return

        tasks[task_id]["progress"] = 30

        # Generate audio
        output_dir = Path("src/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"narration_{task_id}.wav"

        tasks[task_id]["progress"] = 40

        # Process text
        logger.info(f"Processing text ({len(request.text)} chars)...")
        processed = text_processor.process_story(request.text)
        chunks = processed["chunks"]
        text_chunks = [c.text for c in chunks]
        pause_durations = [c.pause_after for c in chunks]

        logger.info(f"Text processed into {len(text_chunks)} chunks")

        tasks[task_id]["progress"] = 50

        # Use different synthesis methods based on synthesizer type
        # Check by class name to avoid issues when RunPodTTSClient is None
        is_runpod = _has_runpod_client and type(synth).__name__ == 'RunPodTTSClient'

        if is_runpod:
            # RunPodTTSClient: synthesize each chunk and combine
            logger.info("Using RunPodTTSClient for synthesis")
            audio_segments = []

            for i, chunk_text in enumerate(text_chunks):
                logger.info(f"Synthesizing chunk {i+1}/{len(text_chunks)}")
                audio_data = synth.synthesize_text(
                    text=chunk_text,
                    voice_sample_path=str(voice_sample_path),
                    exaggeration=request.exaggeration,
                    temperature=request.temperature,
                    cfg_weight=request.cfgWeight
                )
                audio_segments.append(audio_data)
                tasks[task_id]["progress"] = 50 + int(40 * (i + 1) / len(text_chunks))

            # Combine audio segments and save
            with open(output_path, 'wb') as f:
                for segment in audio_segments:
                    f.write(segment)

            result = {"output_path": str(output_path)}

        else:
            # AudioSynthesizer: use set_voice and synthesize_and_save
            logger.info("Using AudioSynthesizer for synthesis")
            synth.set_voice(
                str(voice_sample_path),
                exaggeration=request.exaggeration
            )

            result = synth.synthesize_and_save(
                text_chunks=text_chunks,
                output_path=str(output_path),
                pause_durations=pause_durations,
                format="wav",
                show_progress=False
            )

        tasks[task_id]["progress"] = 90

        # Generate URL for the audio file
        audio_url = f"/output/narration_{task_id}.wav"

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["audio_url"] = audio_url
        tasks[task_id]["completed_at"] = datetime.now().isoformat()
        tasks[task_id]["duration"] = result.get("duration_seconds", 0)

    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)
        tasks[task_id]["progress"] = 0


@router.post("/generate", response_model=TTSGenerateResponse)
async def generate_audio(request: TTSGenerateRequest, background_tasks: BackgroundTasks):
    """
    Generate audio narration for a story
    """
    try:
        # Generate unique task ID
        task_id = str(uuid.uuid4())

        # Initialize task
        tasks[task_id] = {
            "status": "queued",
            "progress": 0,
            "created_at": datetime.now().isoformat(),
            "story_id": request.storyId,
        }

        # Start background task
        background_tasks.add_task(generate_audio_task, task_id, request)

        return TTSGenerateResponse(
            task_id=task_id,
            message="Audio generation started"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start audio generation: {str(e)}")


@router.get("/status/{task_id}", response_model=TTSStatusResponse)
async def get_task_status(task_id: str):
    """
    Get the status of an audio generation task
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]

    # Calculate estimated time remaining
    estimated_time = None
    if task["status"] == "processing" and task["progress"] > 0:
        # Rough estimate: assume 2 minutes total, calculate based on progress
        total_time = 120  # seconds
        elapsed_percentage = task["progress"] / 100
        if elapsed_percentage > 0:
            estimated_time = int(total_time * (1 - elapsed_percentage))

    return TTSStatusResponse(
        status=task["status"],
        progress=task["progress"],
        estimated_time=estimated_time,
        audio_url=task.get("audio_url"),
        error=task.get("error"),
    )
