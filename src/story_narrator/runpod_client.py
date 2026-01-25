"""
RunPod Client for Chatterbox TTS
TEXT + REFERENCE AUDIO (STABLE CONTRACT)
"""

import os
import base64
import requests
from dotenv import load_dotenv
from .logger import setup_logger

load_dotenv()
logger = setup_logger(__name__)


class RunPodTTSClient:
    def __init__(self):
        self.api_key = os.getenv("RUNPOD_API_KEY")
        self.endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID")

        if not self.api_key:
            raise ValueError("RUNPOD_API_KEY not found")
        if not self.endpoint_id:
            raise ValueError("RUNPOD_ENDPOINT_ID not found")

        self.endpoint_url = f"https://api.runpod.ai/v2/{self.endpoint_id}/runsync"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # --------------------------------------------------
    # 🔥 STABLE TTS — TEXT + REFERENCE AUDIO
    # --------------------------------------------------
    def synthesize_with_reference_audio(
        self,
        text: str,
        ref_audio_b64: str,
        exaggeration: float = 0.7,
        temperature: float = 0.8,
        cfg_weight: float = 0.5,
    ) -> bytes:
        """
        Returns RAW WAV BYTES
        """

        payload = {
            "input": {
                "task": "tts",
                "text": text,
                "ref_audio_b64": ref_audio_b64,
                "exaggeration": exaggeration,
                "temperature": temperature,
                "cfg_weight": cfg_weight,
            }
        }

        logger.info(
            f"TTS → chars={len(text)} "
            f"exag={exaggeration} temp={temperature} cfg={cfg_weight}"
        )

        response = requests.post(
            self.endpoint_url,
            headers=self.headers,
            json=payload,
            timeout=600,
        )
        response.raise_for_status()

        result = response.json()
        status = result.get("status")

        if status != "COMPLETED":
            raise RuntimeError(f"RunPod job not completed: {result}")

        output = result.get("output")
        if not output or "audio_b64" not in output:
            raise RuntimeError(f"Invalid RunPod output: {result}")

        # Debug timing (optional but useful)
        exec_time = result.get("executionTime", 0) / 1000
        delay_time = result.get("delayTime", 0) / 1000
        logger.info(
            f"RunPod completed | exec={exec_time:.2f}s wait={delay_time:.2f}s"
        )

        return base64.b64decode(output["audio_b64"])
