"""
Audio Synthesizer
RunPod-based, embedding TTS
PRODUCTION SAFE – FULL AUDIO, CLEAR VOICE
"""

from typing import List, Optional, Dict
import io
import torch
import numpy as np
import soundfile as sf

from .logger import setup_logger
from .runpod_client import RunPodTTSClient
from src.database.voice_service import get_speaker_embedding

logger = setup_logger(__name__)


class AudioSynthesizer:
    def __init__(
        self,
        temperature: float = 0.45,
        cfg_weight: float = 1.05,
    ):
        self.temperature = temperature
        self.cfg_weight = cfg_weight
        self.sample_rate = 24000  # MUST match RunPod output

        logger.info("Initializing RunPod TTS client")
        self.runpod_client = RunPodTTSClient()

    # --------------------------------------------------
    # CORE — CHUNK-BY-CHUNK TTS
    # --------------------------------------------------
    def synthesize_chunks(
        self,
        text_chunks: List[str],
        voice_id: str,
        temperature: Optional[float] = None,
        cfg_weight: Optional[float] = None,
    ) -> torch.Tensor:

        temp = temperature if temperature is not None else self.temperature
        cfg = cfg_weight if cfg_weight is not None else self.cfg_weight

        embedding = get_speaker_embedding(voice_id)
        if not embedding:
            raise RuntimeError(f"No speaker embedding for voice_id={voice_id}")

        audio_segments: List[torch.Tensor] = []

        logger.info("=" * 80)
        logger.info("FINAL TEXT CHUNKS SENT TO RUNPOD:")

        for idx, text in enumerate(text_chunks, 1):
            clean = text.strip()

            if len(clean) < 20:
                logger.warning(f"Skipping tiny chunk: {repr(clean)}")
                continue

            if not clean.endswith((".", "!", "?")):
                clean += "."

            logger.info(
                f"[CHUNK {idx}] chars={len(clean)} words={len(clean.split())}"
            )
            logger.info(f"TEXT → {clean}")

            # 🔥 RunPod returns RAW WAV BYTES
            audio_bytes = self.runpod_client.synthesize_with_embedding(
                text=clean,
                speaker_embedding=embedding,
                temperature=temp,
                cfg_weight=cfg,
            )

            wav = self._decode_wav(audio_bytes)
            audio_segments.append(wav)

        logger.info("=" * 80)

        if not audio_segments:
            raise RuntimeError("No audio chunks generated")

        # 🔥 CONCATENATE ALL AUDIO CHUNKS
        full_audio = torch.cat(audio_segments, dim=-1)
        return full_audio

    # --------------------------------------------------
    # WAV DECODER (RAW BYTES → TORCH)
    # --------------------------------------------------
    def _decode_wav(self, audio_bytes: bytes) -> torch.Tensor:
        buffer = io.BytesIO(audio_bytes)
        wav, sr = sf.read(buffer, dtype="float32")

        if sr != self.sample_rate:
            logger.warning(
                f"Sample rate mismatch: expected {self.sample_rate}, got {sr}"
            )

        if wav.ndim > 1:
            wav = wav.mean(axis=1)

        return torch.from_numpy(wav).unsqueeze(0)

    # --------------------------------------------------
    # SAVE FINAL AUDIO
    # --------------------------------------------------
    def save_audio(self, audio: torch.Tensor, output_path: str):
        audio_np = audio.squeeze(0).cpu().numpy()

        peak = np.max(np.abs(audio_np))
        if peak > 0:
            audio_np = audio_np / peak * 0.95

        sf.write(
            output_path,
            audio_np,
            self.sample_rate,
            format="WAV",
            subtype="PCM_16",
        )

        logger.info(f"✅ Final audio saved → {output_path}")

    # --------------------------------------------------
    # FULL PIPELINE
    # --------------------------------------------------
    def synthesize_and_save(
        self,
        text_chunks: List[str],
        voice_id: str,
        output_path: str,
        temperature: Optional[float] = None,
        cfg_weight: Optional[float] = None,
    ) -> Dict:

        audio = self.synthesize_chunks(
            text_chunks=text_chunks,
            voice_id=voice_id,
            temperature=temperature,
            cfg_weight=cfg_weight,
        )

        self.save_audio(audio, output_path)

        duration = audio.shape[-1] / self.sample_rate

        return {
            "output_path": output_path,
            "duration_seconds": duration,
            "sample_rate": self.sample_rate,
            "chunks": len(text_chunks),
        }