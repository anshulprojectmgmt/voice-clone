# """
# RunPod Serverless Handler for Chatterbox TTS
# Deploy this to your RunPod endpoint for fast GPU-based synthesis
# """
# import runpod
# import torch
# import torchaudio
# import base64
# import io
# import os
# from chatterbox.tts import ChatterboxTTS

# # Global model instance (loaded once on cold start)
# tts_model = None

# def load_model():
#     """Load Chatterbox TTS model (called once on cold start)"""
#     global tts_model
#     if tts_model is None:
#         device = "cuda" if torch.cuda.is_available() else "cpu"
#         print(f"Loading Chatterbox TTS model on {device}...")
#         tts_model = ChatterboxTTS.from_pretrained(device=device)
#         print("Model loaded successfully!")
#     return tts_model

# def handler(job):
#     """
#     RunPod handler function

#     Expected input format:
#     {
#         "task": "tts",
#         "text": "Text to synthesize",
#         "ref_audio_b64": "base64_encoded_voice_sample",
#         "exaggeration": 0.3,
#         "temperature": 0.6,
#         "cfg_weight": 0.3
#     }

#     Returns:
#     {
#         "audio_b64": "base64_encoded_wav_audio"
#     }
#     """
#     try:
#         job_input = job["input"]

#         # Validate input
#         if job_input.get("task") != "tts":
#             return {"error": "Invalid task type. Expected 'tts'"}

#         text = job_input.get("text")
#         ref_audio_b64 = job_input.get("ref_audio_b64")
#         exaggeration = job_input.get("exaggeration", 0.3)
#         temperature = job_input.get("temperature", 0.6)
#         cfg_weight = job_input.get("cfg_weight", 0.3)

#         if not text:
#             return {"error": "Missing 'text' parameter"}
#         if not ref_audio_b64:
#             return {"error": "Missing 'ref_audio_b64' parameter"}

#         # Load model
#         model = load_model()

#         # Decode reference audio
#         print("Decoding reference audio...")
#         ref_audio_bytes = base64.b64decode(ref_audio_b64)
#         ref_audio_buffer = io.BytesIO(ref_audio_bytes)

#         # Save reference audio temporarily
#         temp_ref_path = "/tmp/ref_audio.wav"
#         with open(temp_ref_path, "wb") as f:
#             f.write(ref_audio_bytes)

#         # Prepare voice conditionals
#         print(f"Preparing voice conditionals with exaggeration={exaggeration}...")
#         model.prepare_conditionals(temp_ref_path, exaggeration=exaggeration)

#         # Generate audio
#         print(f"Generating audio for text: {text[:50]}...")
#         wav = model.generate(
#             text,
#             temperature=temperature,
#             cfg_weight=cfg_weight,
#         )

#         # Convert tensor to WAV bytes
#         print("Converting to WAV...")
#         output_buffer = io.BytesIO()
#         torchaudio.save(
#             output_buffer,
#             wav.cpu(),
#             model.sr,
#             format="wav"
#         )
#         output_buffer.seek(0)
#         audio_bytes = output_buffer.read()

#         # Encode as base64
#         audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

#         print(f"Success! Generated {len(audio_bytes)} bytes of audio")

#         # Clean up
#         if os.path.exists(temp_ref_path):
#             os.remove(temp_ref_path)

#         return {
#             "audio_b64": audio_b64,
#             "audio_size_bytes": len(audio_bytes),
#             "sample_rate": model.sr
#         }

#     except Exception as e:
#         print(f"Error in handler: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         return {"error": str(e)}

# # Start the RunPod serverless worker
# runpod.serverless.start({"handler": handler})



# """
# RunPod Serverless Handler
# Embedding-based Chatterbox TTS inference
# """

# import runpod
# import torch
# import torchaudio
# import base64
# import io
# from chatterbox.tts import ChatterboxTTS, Conditionals, T3Cond

# # Global model (loaded once per container)
# tts_model = None


# def load_model():
#     global tts_model
#     if tts_model is None:
#         device = "cuda" if torch.cuda.is_available() else "cpu"
#         print(f"Loading Chatterbox TTS on {device}")
#         tts_model = ChatterboxTTS.from_pretrained(device=device)
#         print("Model loaded")
#     return tts_model


# def handler(job):
#     try:
#         job_input = job["input"]

#         if job_input.get("task") != "tts":
#             return {"error": "Invalid task"}

#         text = job_input.get("text")
#         conds_b64 = job_input.get("speaker_embedding_b64")
#         temperature = job_input.get("temperature", 0.6)
#         cfg_weight = job_input.get("cfg_weight", 0.3)

#         if not text or not conds_b64:
#             return {"error": "Missing text or speaker embedding"}

#         model = load_model()

#         # -------------------------------
#         # Decode speaker embedding
#         # -------------------------------
#         buffer = io.BytesIO(base64.b64decode(conds_b64))
#         payload = torch.load(buffer, map_location=model.device)

#         t3_cond = T3Cond(**payload["t3"]).to(model.device)
#         gen_dict = {
#             k: v.to(model.device) if torch.is_tensor(v) else v
#             for k, v in payload["gen"].items()
#         }

#         model.conds = Conditionals(
#             t3=t3_cond,
#             gen=gen_dict
#         )

#         # -------------------------------
#         # Generate audio
#         # -------------------------------
#         with torch.inference_mode():
#             wav = model.generate(
#                 text=text,
#                 temperature=temperature,
#                 cfg_weight=cfg_weight,
#             )

#         # Convert to WAV bytes
#         out_buf = io.BytesIO()
#         torchaudio.save(out_buf, wav.cpu(), model.sr, format="wav")
#         out_buf.seek(0)

#         audio_b64 = base64.b64encode(out_buf.read()).decode("utf-8")

#         return {
#             "audio_b64": audio_b64,
#             "sample_rate": model.sr,
#         }

#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         return {"error": str(e)}


# runpod.serverless.start({"handler": handler})


import runpod
import torch
import torchaudio
import base64
import io
import os
import numpy as np
from chatterbox.tts import ChatterboxTTS

tts_model = None


def load_model():
    global tts_model
    if tts_model is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[RunPod] Loading Chatterbox TTS on {device}")
        tts_model = ChatterboxTTS.from_pretrained(device=device)
        print("[RunPod] Model loaded")
    return tts_model


def decode_audio(b64_audio: str) -> str:
    audio_bytes = base64.b64decode(b64_audio)
    temp_path = "/tmp/ref.wav"
    with open(temp_path, "wb") as f:
        f.write(audio_bytes)
    return temp_path


def handler(job):
    try:
        inp = job["input"]
        task = inp.get("task")

        model = load_model()

        # ----------------------------------
        # TASK 1: EXTRACT SPEAKER EMBEDDING
        # ----------------------------------
        if task == "extract_embedding":
            ref_audio_b64 = inp.get("ref_audio_b64")
            if not ref_audio_b64:
                return {"error": "ref_audio_b64 missing"}

            wav_path = decode_audio(ref_audio_b64)

            embedding = model.extract_speaker_embedding(wav_path)

            os.remove(wav_path)

            return {
                "speaker_embedding": embedding.tolist(),
                "embedding_dim": len(embedding)
            }

        # ----------------------------------
        # TASK 2: TTS WITH EMBEDDING
        # ----------------------------------
        elif task == "tts_with_embedding":
            text = inp.get("text")
            embedding = inp.get("speaker_embedding")

            if not text or embedding is None:
                return {"error": "text or speaker_embedding missing"}

            exaggeration = inp.get("exaggeration", 0.5)
            temperature = inp.get("temperature", 0.8)
            cfg_weight = inp.get("cfg_weight", 0.5)

            # Rebuild conditionals using embedding
            embedding_tensor = torch.tensor(
                embedding, dtype=torch.float32
            ).unsqueeze(0).to(model.device)

            model.conds.t3.speaker_emb = embedding_tensor
            model.conds.t3.emotion_adv = exaggeration * torch.ones(
                1, 1, 1, device=model.device
            )

            wav = model.generate(
                text,
                temperature=temperature,
                cfg_weight=cfg_weight
            )

            buf = io.BytesIO()
            torchaudio.save(buf, wav.cpu(), model.sr, format="wav")
            audio_b64 = base64.b64encode(buf.getvalue()).decode()

            return {
                "audio_b64": audio_b64,
                "sample_rate": model.sr
            }

        else:
            return {"error": f"Invalid task: {task}"}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


runpod.serverless.start({"handler": handler})
