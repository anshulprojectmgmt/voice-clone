"""
RunPod Client for Chatterbox TTS (Embedding-Based Inference)
"""

import os
import base64
import requests
from dotenv import load_dotenv
from typing import List

load_dotenv()


class RunPodTTSClient:
    """
    Sends text + speaker embeddings to RunPod
    """

    def __init__(self):
        self.api_key = os.getenv("RUNPOD_API_KEY")
        self.endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID")

        if not self.api_key:
            raise ValueError("RUNPOD_API_KEY missing")
        if not self.endpoint_id:
            raise ValueError("RUNPOD_ENDPOINT_ID missing")

        self.endpoint_url = f"https://api.runpod.ai/v2/{self.endpoint_id}/runsync"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ================================
    # 1️⃣ EXTRACT SPEAKER EMBEDDING
    # ================================
    def extract_embedding(self, audio_b64: str) -> dict:
        payload = {
            "input": {
                "task": "extract_embedding",
                "audio_b64": audio_b64,
            }
        }

        response = requests.post(
            self.endpoint_url,
            headers=self.headers,
            json=payload,
            timeout=300,
        )
        response.raise_for_status()

        result = response.json()
        return result.get("output", result)

    # ================================
    # 2️⃣ TTS USING EMBEDDING (FIXED)
    # ================================
    def synthesize_with_embedding(
        self,
        text:str,
        speaker_embedding: dict,
        temperature: float = 0.8,
        cfg_weight: float = 0.5,
    ) -> bytes:
        print(text)
        payload = {
            "input": {
                "task": "tts",
                "text": text,
                "speaker_embedding": speaker_embedding,
                "temperature": temperature,
                "cfg_weight": cfg_weight,
            }
        }
        
        response = requests.post(
            self.endpoint_url,
            headers=self.headers,
            json=payload,
            timeout=300,
        )
        response.raise_for_status()

        result = response.json()

        if "output" not in result or "audio_b64" not in result["output"]:
            raise RuntimeError(f"Invalid RunPod response: {result}")

        return base64.b64decode(result["output"]["audio_b64"])