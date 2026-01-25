# """
# TTS API Routes
# Embedding-based TTS using StoryNarrator (FINAL)
# """

# from fastapi import APIRouter, Depends, HTTPException
# from pydantic import BaseModel
# from typing import Optional
# from pathlib import Path
# import uuid
# import logging

# from ...auth.dependencies import get_optional_user
# from ...database.voice_service import get_voice_by_id, increment_usage
# from ...story_narrator.narrator import StoryNarrator
# from ...story_narrator.story_generator import StoryPrompt

# router = APIRouter(prefix="/api/v1/tts", tags=["tts"])
# logger = logging.getLogger(__name__)

# OUTPUT_DIR = Path("src/output/audio")
# OUTPUT_DIR.mkdir(parents=True, exist_ok=True)



# # ----------------------------
# # REQUEST / RESPONSE MODELS
# # ----------------------------

# class TTSGenerateRequest(BaseModel):
#     voice_id: str

#     # Either direct text OR story params
#     text: Optional[str] = None
#     theme: Optional[str] = None
#     style: str = "adventure"
#     tone: str = "engaging"
#     length: str = "medium"

#     temperature: float = 0.55
#     cfg_weight: float = 0.25


# class TTSGenerateResponse(BaseModel):
#     audio_url: str
#     voice_id: str


# # ----------------------------
# # MAIN ENDPOINT
# # ----------------------------

# @router.post("/generate", response_model=TTSGenerateResponse)
# async def generate_tts(
#     request: TTSGenerateRequest,
#     user: Optional[dict] = Depends(get_optional_user),
# ):
#     user_id = user["id"] if user else None

#     # ----------------------------
#     # Validate voice
#     # ----------------------------

    
#     voice = get_voice_by_id(request.voice_id)
#     if not voice:
#         raise HTTPException(status_code=404, detail="Voice not found")
#     logger.info(f"TTS requested with voice_id={request.voice_id}")
#     # Allow:
#     # - owner
#     # - system voice (user_id = 1)
#     if user_id and voice.user_id not in (user_id, 1):
#         raise HTTPException(status_code=403, detail="Access denied")

#     # ----------------------------
#     # Prepare output
#     # ----------------------------
#     output_path = OUTPUT_DIR / f"{uuid.uuid4().hex}.wav"

#     narrator = StoryNarrator()

#     # ----------------------------
#     # TEXT-ONLY TTS
#     # ----------------------------
#     if request.text:
#         narrator.narrate_existing_story(
#             story_text=request.text,
#             voice_id=request.voice_id,
#             output_path=str(output_path),
#             temperature=max(0.25, min(request.temperature, 0.45)),
#             cfg_weight=max(0.7, min(request.cfg_weight, 1.0)),

#         )

#     # ----------------------------
#     # STORY GENERATION + TTS
#     # ----------------------------
#     elif request.theme:
#         prompt = StoryPrompt(
#             theme=request.theme,
#             style=request.style,
#             tone=request.tone,
#             length=request.length,
#         )

#         narrator.create_story_narration(
#             story_prompt=prompt,
#             voice_id=request.voice_id,
#             output_path=str(output_path),
#             temperature=request.temperature,
#             cfg_weight=request.cfg_weight,
#         )

#     else:
#         raise HTTPException(
#             status_code=400,
#             detail="Either `text` or `theme` must be provided",
#         )

#     # ----------------------------
#     # Update usage stats
#     # ----------------------------
#     increment_usage(request.voice_id)

#     return TTSGenerateResponse(
#         audio_url=f"/output/audio/{output_path.name}",
#         voice_id=request.voice_id,
#     )



"""
TTS API Routes
Embedding-based TTS using StoryNarrator (FINAL – FIXED)
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import uuid
import logging

from ...auth.dependencies import get_optional_user
from ...database.voice_service import get_voice_by_id, increment_usage
from ...story_narrator.narrator import StoryNarrator
from ...story_narrator.story_generator import StoryPrompt

router = APIRouter(prefix="/api/v1/tts", tags=["tts"])
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("src/output/audio")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# REQUEST / RESPONSE MODELS
# ----------------------------

class TTSGenerateRequest(BaseModel):
    voice_id: str

    # Either direct text OR story params
    text: Optional[str] = None
    theme: Optional[str] = None
    style: str = "adventure"
    tone: str = "engaging"
    length: str = "medium"

    # ✅ SAFE DEFAULTS FOR NATURAL LONG SPEECH
    temperature: float = 0.8
    cfg_weight: float = 0.5


class TTSGenerateResponse(BaseModel):
    audio_url: str
    voice_id: str


# ----------------------------
# MAIN ENDPOINT
# ----------------------------

@router.post("/generate", response_model=TTSGenerateResponse)
async def generate_tts(
    request: TTSGenerateRequest,
    user: Optional[dict] = Depends(get_optional_user),
):
    user_id = user["id"] if user else None

    # ----------------------------
    # Validate voice from db
    # ----------------------------
    voice = get_voice_by_id(request.voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found")

    logger.info(
        f"TTS request | voice_id={request.voice_id} "
        f"text_len={len(request.text) if request.text else 0} "
        f"temperature={request.temperature} "
        f"cfg_weight={request.cfg_weight}"
    )

    # Allow:
    # - owner
    # - system voice (user_id = 1)
    if user_id and voice.user_id not in (user_id, 1):
        raise HTTPException(status_code=403, detail="Access denied")

    # ----------------------------
    # Prepare output
    # ----------------------------
    output_path = OUTPUT_DIR / f"{uuid.uuid4().hex}.wav"
    narrator = StoryNarrator()

    # ----------------------------
    # TEXT-ONLY TTS
    # ----------------------------
    if request.text:
        narrator.narrate_existing_story(
            story_text=request.text,
            voice_id=request.voice_id,
            output_path=str(output_path),
            temperature=request.temperature,
            cfg_weight=request.cfg_weight,
        )
         

    # ----------------------------
    # STORY GENERATION + TTS
    # ----------------------------
    elif request.theme:
        prompt = StoryPrompt(
            theme=request.theme,
            style=request.style,
            tone=request.tone,
            length=request.length,
        )

        narrator.create_story_narration(
            story_prompt=prompt,
            voice_id=request.voice_id,
            output_path=str(output_path),
            temperature=request.temperature,
            cfg_weight=request.cfg_weight,
        )

    else:
        raise HTTPException(
            status_code=400,
            detail="Either `text` or `theme` must be provided",
        )

    # ----------------------------
    # Update usage stats
    # ----------------------------
    increment_usage(request.voice_id)

    return TTSGenerateResponse(
        audio_url=f"/output/audio/{output_path.name}",
        voice_id=request.voice_id,
    )