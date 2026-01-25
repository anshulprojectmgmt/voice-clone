"""
RunPod Client for Chatterbox TTS
Handles remote synthesis via RunPod serverless endpoint
"""
import os
import base64
import time
import requests
from pathlib import Path
from dotenv import load_dotenv
from .logger import setup_logger

load_dotenv()
logger = setup_logger(__name__)

class RunPodTTSClient:
    def __init__(self):
        self.api_key = os.getenv("RUNPOD_API_KEY")
        self.endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID")

        if not self.api_key:
            raise ValueError("RUNPOD_API_KEY not found in .env")
        if not self.endpoint_id:
            raise ValueError("RUNPOD_ENDPOINT_ID not found in .env")

        # Use direct API endpoint as per RunPod guide
        self.endpoint_url = f"https://api.runpod.ai/v2/{self.endpoint_id}/runsync"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def synthesize_text(
        self,
        text: str,
        voice_sample_path: str,
        exaggeration: float = 0.3,
        temperature: float = 0.6,
        cfg_weight: float = 0.3
    ):
        """
        Synthesize speech from text using RunPod endpoint
        
        Args:
            text: Text to synthesize
            voice_sample_path: Path to reference voice audio file
            exaggeration: Voice emotion strength (0.0-1.0)
            temperature: Sampling temperature (0.0-1.5)
            cfg_weight: Classifier-free guidance weight (0.0-1.0)
        
        Returns:
            bytes: WAV audio data
        """
        # Read and encode voice sample
        with open(voice_sample_path, "rb") as f:
            voice_b64 = base64.b64encode(f.read()).decode('utf-8')
        
        # Prepare RunPod request with all TTS parameters
        request_payload = {
            "input": {
                "task": "tts",
                "text": text,
                "ref_audio_b64": voice_b64,
                "exaggeration": exaggeration,
                "temperature": temperature,
                "cfg_weight": cfg_weight
            }
        }

        logger.info(f"TTS params - exaggeration: {exaggeration}, temperature: {temperature}, cfg_weight: {cfg_weight}")
        logger.info(f"Synthesizing text ({len(text)} chars): {text[:100]}...")

        logger.info(f"Sending request to RunPod endpoint: {self.endpoint_url}")
        logger.info("Note: First request may take 30-60s (cold start)...")

        try:
            # Send request to RunPod API
            response = requests.post(
                self.endpoint_url,
                headers=self.headers,
                json=request_payload,
                timeout=300  # 5 minutes max wait
            )
            response.raise_for_status()  # Raise exception for HTTP errors

            # Parse response
            result = response.json()
            logger.info(f"RunPod response status: {result.get('status')}")

            # Check if job completed successfully
            status = result.get('status', 'UNKNOWN')

            if status == 'COMPLETED':
                output = result.get('output', {})

                # Get audio from output
                if "audio_b64" in output:
                    audio_bytes = base64.b64decode(output["audio_b64"])
                    exec_time = result.get('executionTime', 0) / 1000  # Convert ms to seconds
                    delay_time = result.get('delayTime', 0) / 1000
                    logger.info(f"Job completed! Audio: {len(audio_bytes)} bytes (exec: {exec_time:.1f}s, wait: {delay_time:.1f}s)")
                    return audio_bytes
                else:
                    raise RuntimeError(f"No audio_b64 in output. Output keys: {list(output.keys())}")

            elif status == 'FAILED':
                error_msg = result.get('error', 'Unknown error')
                raise RuntimeError(f"Job failed: {error_msg}")

            else:
                # Unexpected status
                raise RuntimeError(f"Unexpected status: {status}. Response: {result}")

        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request failed: {e}")
            raise RuntimeError(f"Failed to connect to RunPod: {e}")
        except Exception as e:
            logger.error(f"RunPod synthesis failed: {e}")
            raise
    
    def synthesize_chunks(
        self,
        chunks: list,
        voice_sample_path: str,
        exaggeration: float = 0.3,
        temperature: float = 0.6,
        cfg_weight: float = 0.3,
        progress_callback=None
    ):
        """
        Synthesize multiple text chunks
        
        Args:
            chunks: List of text chunks
            voice_sample_path: Path to reference voice
            exaggeration, temperature, cfg_weight: TTS parameters
            progress_callback: Optional callback(current, total) for progress
        
        Returns:
            list: List of audio bytes for each chunk
        """
        audio_segments = []
        total = len(chunks)
        
        for i, chunk in enumerate(chunks, 1):
            if progress_callback:
                progress_callback(i, total)

            logger.info(f"Synthesizing chunk {i}/{total}...")
            audio_bytes = self.synthesize_text(
                text=chunk,
                voice_sample_path=voice_sample_path,
                exaggeration=exaggeration,
                temperature=temperature,
                cfg_weight=cfg_weight
            )
            audio_segments.append(audio_bytes)
            logger.info(f"Chunk {i}/{total} completed")
        
        return audio_segments


def test_runpod_client():
    """Quick test of RunPod client"""
    client = RunPodTTSClient()

    # Test with short text
    test_text = "Hello, this is a test of the RunPod TTS system."
    # Look for voice sample in samples directory
    root = Path(__file__).parents[2]
    voice_path = root / "samples" / "REALTYAI.wav"

    if not voice_path.exists():
        logger.error(f"Voice file not found: {voice_path}")
        return

    logger.info("Testing RunPod TTS client...")
    audio = client.synthesize_text(
        text=test_text,
        voice_sample_path=str(voice_path)
    )

    # Save output
    output_path = "test_runpod_output.wav"
    with open(output_path, "wb") as f:
        f.write(audio)

    logger.info(f"Test successful! Audio saved to: {output_path}")


if __name__ == "__main__":
    test_runpod_client()
