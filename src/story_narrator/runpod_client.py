"""
RunPod Client for Chatterbox TTS
TEXT + REFERENCE AUDIO (STABLE CONTRACT)
"""

import os
import base64
import time
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
        exaggeration: float = 0.3,
        temperature: float = 0.85,
        cfg_weight: float = 0.2,
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

        # ✅ ALWAYS extract job_id immediately
        job_id = result.get("id")
        if not job_id:
            raise RuntimeError(f"RunPod response missing job id: {result}")

        # ✅ HANDLE QUEUE / PROGRESS (cold starts)
        if result.get("status") in ("IN_QUEUE", "IN_PROGRESS"):
            for _ in range(30):  # ~36 seconds max
                time.sleep(1.2)

                status_resp = requests.get(
                    f"https://api.runpod.ai/v2/{self.endpoint_id}/status/{job_id}",
                    headers=self.headers,
                    timeout=30,
                )
                status_resp.raise_for_status()
                result = status_resp.json()

                if result.get("status") == "COMPLETED":
                    break

        # ❌ STILL NOT DONE → REAL FAILURE
        if result.get("status") != "COMPLETED":
            raise RuntimeError(f"RunPod job not completed: {result}")

        output = result.get("output")
        if not output or "audio_b64" not in output:
            raise RuntimeError(f"Invalid RunPod output: {result}")

        # Optional debug timing
        exec_time = result.get("executionTime", 0) / 1000
        delay_time = result.get("delayTime", 0) / 1000
        logger.info(
            f"RunPod completed | exec={exec_time:.2f}s wait={delay_time:.2f}s"
        )

        return base64.b64decode(output["audio_b64"])
