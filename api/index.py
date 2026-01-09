"""
Vercel entrypoint for VoiceClone API
Imports the FastAPI app from src.api.main
"""
from src.api.main import app

# This is the entrypoint that Vercel will use
__all__ = ["app"]
