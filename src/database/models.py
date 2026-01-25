"""
Database Models
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import json


# =========================================================
# USER
# =========================================================

@dataclass
class User:
    """User database model"""
    id: int
    username: str
    email: str
    password_hash: str
    is_active: bool
    is_verified: bool
    created_at: str
    updated_at: str
    last_login: Optional[str] = None
    metadata: Optional[dict] = None

    @classmethod
    def from_db_row(cls, row):
        return cls(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            password_hash=row["password_hash"],
            is_active=bool(row["is_active"]),
            is_verified=bool(row["is_verified"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_login=row.get("last_login"),
            metadata=json.loads(row["metadata"]) if row.get("metadata") else None,
        )

    def to_dict(self, include_password=False):
        def to_str(v):
            if isinstance(v, datetime):
                return v.isoformat()
            return v

        data = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "created_at": to_str(self.created_at),
            "updated_at": to_str(self.updated_at),
            "last_login": to_str(self.last_login) if self.last_login else None,
            "metadata": self.metadata,
        }

        if include_password:
            data["password_hash"] = self.password_hash

        return data


# =========================================================
# VOICE PROFILE  (🔥 MOST IMPORTANT FIX)
# =========================================================

@dataclass
class VoiceProfile:
    """
    Voice Profile database model
    - Embeddings are stored DIRECTLY in DB (JSON)
    - Used by RunPod TTS
    """
    id: int
    user_id: int
    voice_id: str
    name: str
    file_path: str

    # 🔑 REQUIRED FOR EMBEDDING-BASED TTS
    speaker_embedding: Optional[str]

    sample_rate: int
    duration: Optional[float]
    exaggeration: float
    is_default: bool
    created_at: str
    updated_at: str

    description: Optional[str] = None
    last_used: Optional[str] = None
    usage_count: int = 0

    @classmethod
    def from_db_row(cls, row):
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            voice_id=row["voice_id"],
            name=row["name"],
            file_path=row["file_path"],
            speaker_embedding=row.get("speaker_embedding"),
            sample_rate=row["sample_rate"],
            duration=row.get("duration"),
            exaggeration=float(row["exaggeration"]),
            is_default=bool(row["is_default"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            description=row.get("description"),
            last_used=row.get("last_used"),
            usage_count=row.get("usage_count", 0),
        )

    def to_dict(self):
        """
        IMPORTANT:
        - speaker_embedding is NEVER exposed to frontend
        """
        def to_str(v):
            if isinstance(v, datetime):
                return v.isoformat()
            return v

        return {
            "id": self.id,
            "user_id": self.user_id,
            "voice_id": self.voice_id,
            "name": self.name,
            "description": self.description,
            "file_path": self.file_path,
            "sample_rate": self.sample_rate,
            "duration": self.duration,
            "exaggeration": self.exaggeration,
            "is_default": self.is_default,
            "created_at": to_str(self.created_at),
            "updated_at": to_str(self.updated_at),
            "last_used": to_str(self.last_used) if self.last_used else None,
            "usage_count": self.usage_count,
        }


# =========================================================
# REFRESH TOKEN
# =========================================================

@dataclass
class RefreshToken:
    id: int
    user_id: int
    token: str
    expires_at: str
    created_at: str
    is_revoked: bool
    revoked_at: Optional[str] = None

    @classmethod
    def from_db_row(cls, row):
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            token=row["token"],
            expires_at=row["expires_at"],
            created_at=row["created_at"],
            is_revoked=bool(row["is_revoked"]),
            revoked_at=row.get("revoked_at"),
        )

    def to_dict(self):
        def to_str(v):
            if isinstance(v, datetime):
                return v.isoformat()
            return v

        return {
            "id": self.id,
            "user_id": self.user_id,
            "token": self.token,
            "expires_at": to_str(self.expires_at),
            "created_at": to_str(self.created_at),
            "is_revoked": self.is_revoked,
            "revoked_at": to_str(self.revoked_at) if self.revoked_at else None,
        }


# =========================================================
# STORY
# =========================================================

@dataclass
class Story:
    id: str
    title: str
    text: str
    theme: str
    style: str
    tone: str
    length: str
    word_count: int
    thumbnail_color: str
    preview_text: str
    created_at: str
    updated_at: str
    audio_url: Optional[str] = None
    metadata: Optional[dict] = None

    @classmethod
    def from_db_row(cls, row):
        return cls(
            id=row["id"],
            title=row.get("title") or "",
            text=row["text"],
            theme=row["theme"],
            style=row["style"],
            tone=row["tone"],
            length=row["length"],
            word_count=row["word_count"],
            thumbnail_color=row.get("thumbnail_color") or "",
            preview_text=row.get("preview_text") or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            audio_url=row.get("audio_url"),
            metadata=json.loads(row["metadata"]) if row.get("metadata") else None,
        )

    def to_dict(self):
        def to_str(v):
            if isinstance(v, datetime):
                return v.isoformat()
            return v

        return {
            "id": self.id,
            "title": self.title,
            "text": self.text,
            "theme": self.theme,
            "style": self.style,
            "tone": self.tone,
            "length": self.length,
            "word_count": self.word_count,
            "thumbnail_color": self.thumbnail_color,
            "preview_text": self.preview_text,
            "created_at": to_str(self.created_at),
            "updated_at": to_str(self.updated_at),
            "audio_url": self.audio_url,
            "metadata": self.metadata,
        }
