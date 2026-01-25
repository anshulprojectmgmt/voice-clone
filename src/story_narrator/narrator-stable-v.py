"""
Story Narrator - Main orchestrator (PRODUCTION SAFE)
"""

from typing import Dict, Optional, List
from pathlib import Path
import json
from datetime import datetime
import re

from dotenv import load_dotenv
from .logger import setup_logger
from .story_generator import StoryGenerator, StoryPrompt
from .audio_synthesizer import AudioSynthesizer

load_dotenv()
logger = setup_logger(__name__)


# =====================================================
# 🔪 SINGLE SOURCE OF TRUTH — CHUNKING
# =====================================================
def split_into_safe_chunks(text: str, max_chars: int = 140) -> List[str]:
    """
    Sentence-aware, chatterbox-safe chunking
    """
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks: List[str] = []
    current = ""

    for s in sentences:
        s = s.strip()
        if not s:
            continue

        if len(current) + len(s) <= max_chars:
            current = f"{current} {s}".strip()
        else:
            chunks.append(current)
            current = s

    if current:
        chunks.append(current)

    return chunks


class StoryNarrator:
    def __init__(
        self,
        llm_provider: str = "gemini",
        llm_api_key: Optional[str] = None,
        llm_model: Optional[str] = None,
    ):
        logger.info("Initializing Story Narrator system...")
        logger.info("TTS backend: RunPod (embedding-based)")

        self.story_generator = StoryGenerator(
            provider=llm_provider,
            api_key=llm_api_key,
            model=llm_model
        )

        self.audio_synthesizer = AudioSynthesizer()
        logger.info("Story Narrator initialized successfully")

    # --------------------------------------------------
    # TEXT ONLY TTS
    # --------------------------------------------------
    def narrate_existing_story(
        self,
        story_text: str,
        voice_id: str,
        output_path: str,
        temperature: float = 0.45,
        cfg_weight: float = 0.55,
    ) -> Dict:

        # 🚫 NEVER log raw story text
        logger.info(
            "Narrating story | chars=%d words=%d",
            len(story_text),
            len(story_text.split()),
        )

        text_chunks = split_into_safe_chunks(story_text)

        # 🔍 DEBUG — SEE EXACT CHUNKS
        logger.info("=" * 80)
        logger.info("FINAL TEXT CHUNKS SENT TO TTS:")
        for i, c in enumerate(text_chunks, 1):
            logger.info(f"[CHUNK {i}] chars={len(c)} words={len(c.split())}")
            logger.info(f"TEXT → {c}")
        logger.info("=" * 80)

        self.audio_synthesizer.temperature = temperature
        self.audio_synthesizer.cfg_weight = cfg_weight

        audio_result = self.audio_synthesizer.synthesize_and_save(
            text_chunks=text_chunks,
            voice_id=voice_id,
            output_path=output_path,
        )

        return audio_result