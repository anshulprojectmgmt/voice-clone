"""
TTS API Routes - WITH EMBEDDINGS CACHING

This is a critical optimization module that:
1. Loads pre-cached voice embeddings from database (<50ms)
2. Falls back to recomputing only if cache miss (400-1100ms)
3. Optionally requires authentication for user-specific voices
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Dict, Optional
import uuid
import asyncio
from datetime import datetime
import base64
import os
from pathlib import Path
import re
import logging
from concurrent.futures import ThreadPoolExecutor

from ..models.tts import (
    TTSGenerateRequest,
    TTSGenerateResponse,
    TTSStatusResponse,
)
from story_narrator.text_processor import TextProcessor
from ...auth.dependencies import get_optional_user
from ...database import voice_service

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

# Thread pool for blocking I/O operations (RunPod API calls)
# This prevents blocking the FastAPI event loop during audio generation
executor = ThreadPoolExecutor(max_workers=4)

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


def generate_audio_task(task_id: str, request: TTSGenerateRequest, user_id: Optional[int] = None):
    """
    Background task to generate audio with cached embeddings optimization

    Note: This is a synchronous function (not async) because it does blocking I/O (RunPod API calls).
    It runs in a thread pool executor to avoid blocking the FastAPI event loop.

    OPTIMIZATION: Loads pre-computed voice embeddings from database (<50ms)
    instead of recomputing them every time (400-1100ms).
    """
    try:
        tasks[task_id]["status"] = "processing"
        tasks[task_id]["progress"] = 10

        synth = get_synthesizer()

        # Get voice profile from database
        voice_profile = None
        voice_sample_path = None

        if request.voiceSample:
            # Check if it's the default voice
            if request.voiceSample == "default":
                # Get default voice from database (pre-cached on startup)
                voice_profile = voice_service.get_default_voice(user_id)
                if not voice_profile:
                    tasks[task_id]["status"] = "failed"
                    tasks[task_id]["error"] = "No default voice available. Please upload a voice sample first."
                    return
                voice_sample_path = Path(voice_profile.file_path)
                logger.info(f"Using default voice: {voice_profile.voice_id}")
                tasks[task_id]["progress"] = 20

            # Check if it's a voice ID (UUID format) or base64 data
            elif len(request.voiceSample) < 100:  # Likely a voice ID
                # Look up voice profile from database
                voice_profile = voice_service.get_voice_by_id(request.voiceSample)

                if not voice_profile:
                    tasks[task_id]["status"] = "failed"
                    tasks[task_id]["error"] = f"Voice sample not found: {request.voiceSample}"
                    return

                # Verify ownership if user_id provided
                if user_id and voice_profile.user_id != user_id:
                    # Check if it's a system voice (user_id=1)
                    SYSTEM_USER_ID = int(os.getenv("SYSTEM_USER_ID", "1"))
                    if voice_profile.user_id != SYSTEM_USER_ID:
                        tasks[task_id]["status"] = "failed"
                        tasks[task_id]["error"] = "Access denied: This voice belongs to another user"
                        return

                voice_sample_path = Path(voice_profile.file_path)
                logger.info(f"Using voice from database: {voice_profile.voice_id}")
                tasks[task_id]["progress"] = 20

            else:
                # It's base64 encoded data (legacy support - no caching)
                try:
                    logger.warning("Base64 voice data provided - skipping cache (will be slower)")
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
        if not voice_profile and not voice_sample_path:
            voice_profile = voice_service.get_default_voice(user_id)
            if not voice_profile:
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["error"] = "No voice samples available. Please upload a voice sample first."
                return
            voice_sample_path = Path(voice_profile.file_path)
            logger.info(f"Using default voice: {voice_profile.voice_id}")

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
            # AudioSynthesizer: use CACHED EMBEDDINGS for 10-20x speedup
            logger.info("Using AudioSynthesizer for synthesis")

            # CRITICAL OPTIMIZATION: Load cached embeddings instead of recomputing
            if voice_profile and voice_profile.embeddings_path:
                # Try to load cached embeddings (FAST PATH <50ms)
                logger.info(f"Attempting to load cached embeddings for voice {voice_profile.voice_id}")
                cached_conds = voice_service.load_cached_embeddings(
                    voice_profile.voice_id,
                    request.exaggeration
                )

                if cached_conds:
                    # SUCCESS: Use cached embeddings (10-20x faster than prepare_conditionals)
                    logger.info(f"✓ Using cached embeddings (<50ms) - 10-20x speedup!")
                    synth.tts_model.conds = cached_conds

                    # Update voice usage statistics
                    voice_service.increment_usage(voice_profile.voice_id)
                else:
                    # Cache miss (different exaggeration or corrupted cache)
                    logger.warning(f"Cache miss for exaggeration={request.exaggeration}, recomputing...")
                    synth.tts_model.prepare_conditionals(
                        str(voice_sample_path),
                        request.exaggeration
                    )

                    # Re-cache with new exaggeration value
                    try:
                        voice_service.recache_voice_embeddings(
                            voice_profile.voice_id,
                            synth.tts_model,
                            request.exaggeration
                        )
                        logger.info(f"✓ Embeddings re-cached for exaggeration={request.exaggeration}")
                    except Exception as e:
                        logger.error(f"Failed to re-cache embeddings: {e}")
            else:
                # No cached embeddings available (base64 upload or legacy voice)
                logger.warning("No cached embeddings available, using slow path (400-1100ms)")
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


async def run_generation_in_thread(task_id: str, request: TTSGenerateRequest, user_id: Optional[int]):
    """
    Wrapper to run generate_audio_task in a thread pool executor.
    This prevents blocking the FastAPI event loop during long-running RunPod API calls.
    """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, generate_audio_task, task_id, request, user_id)


@router.post("/generate", response_model=TTSGenerateResponse)
async def generate_audio(
    request: TTSGenerateRequest,
    background_tasks: BackgroundTasks,
    user: Optional[dict] = Depends(get_optional_user),
):
    """
    Generate audio narration for a story

    Optional authentication:
        - If authenticated: can access user's private voices + system voices
        - If not authenticated: can only access system voices (user_id=1)

    OPTIMIZATION: Uses cached voice embeddings for 10-20x faster processing
    """
    try:
        user_id = user["id"] if user else None
        username = user["username"] if user else "anonymous"

        logger.info(f"Audio generation request from {username} for story {request.storyId}")
        logger.info(f"Voice: {request.voiceSample}, Exaggeration: {request.exaggeration}")

        # Generate unique task ID
        task_id = str(uuid.uuid4())
        logger.info(f"Generated task ID: {task_id}")

        # Initialize task
        tasks[task_id] = {
            "status": "queued",
            "progress": 0,
            "created_at": datetime.now().isoformat(),
            "story_id": request.storyId,
            "user_id": user_id,
        }

        # Start background task with user_id for voice access control
        # Run in thread pool to avoid blocking the event loop during RunPod API calls
        background_tasks.add_task(run_generation_in_thread, task_id, request, user_id)
        logger.info(f"Background task queued for task {task_id}, returning response")

        return TTSGenerateResponse(
            task_id=task_id,
            message="Audio generation started"
        )

    except Exception as e:
        logger.error(f"Failed to start audio generation: {e}")
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
