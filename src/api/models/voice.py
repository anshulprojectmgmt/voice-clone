"""
Voice API Models
"""
from pydantic import BaseModel, Field
from typing import List
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
    uploaded_at: str = Field(..., description="Upload timestamp")
    sample_url: str = Field(..., description="URL to the voice sample")
    duration: float = Field(..., description="Duration in seconds")


class VoiceLibraryResponse(BaseModel):
    voices: List[VoiceLibraryItem] = Field(default_factory=list, description="List of voice samples")
