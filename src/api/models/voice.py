"""
Voice API Models
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class VoiceUploadResponse(BaseModel):
    voice_id: str = Field(..., description="Unique voice identifier")
    name: str = Field(..., description="Voice name")
    sample_url: str = Field(..., description="URL to the uploaded voice sample")
    duration: float = Field(..., description="Duration of the voice sample in seconds")
    sample_rate: int = Field(..., description="Sample rate of the audio")
    embeddings_cached: bool = Field(..., description="Whether embeddings are pre-computed")
    is_default: bool = Field(..., description="Whether this is the user's default voice")


class VoiceLibraryItem(BaseModel):
    voice_id: str = Field(..., description="Unique voice identifier")
    name: str = Field(..., description="Voice sample name")
    sample_url: str = Field(..., description="URL to the voice sample")
    duration: float = Field(..., description="Duration in seconds")

    # ✅ OPTIONAL — FIXES YOUR ERROR
    uploaded_at: Optional[datetime] = Field(
        default=None,
        description="Upload timestamp",
    )

    embeddings_cached: bool = Field(
        default=False,
        description="Whether embeddings are cached",
    )

    is_default: bool = Field(
        default=False,
        description="Whether this is default voice",
    )


class VoiceLibraryResponse(BaseModel):
    voices: List[VoiceLibraryItem] = Field(
        default_factory=list,
        description="List of voice samples",
    )
