"""
VoiceClone FastAPI Backend
Main application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging
import os

from .routes import story, tts, voice, stories

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="VoiceClone API",
    description="AI-powered story generation and narration with voice cloning",
    version="1.0.0",
)

# Configure CORS - support both local development and production
frontend_url = os.getenv("FRONTEND_URL", "").strip()
environment = os.getenv("ENVIRONMENT", "development")

# Development origins
allowed_origins = [
    "http://localhost:3000",  # Next.js dev server
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# Add production frontend URL if set
if frontend_url:
    # Handle both with and without protocol
    if not frontend_url.startswith(('http://', 'https://')):
        allowed_origins.extend([
            f"https://{frontend_url}",
            f"http://{frontend_url}",
        ])
    else:
        allowed_origins.append(frontend_url)
    logger.info(f"Added production frontend URL to CORS: {frontend_url}")

# For production, also allow all .onrender.com domains
if environment == "production":
    logger.info("Production mode: allowing .onrender.com origins")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if environment != "production" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if environment == "production":
    logger.warning("CORS is set to allow all origins (*) in production. This should be restricted in a real deployment.")

# Mount static files (for serving generated audio and voice samples)
output_dir = Path("src/output")
output_dir.mkdir(parents=True, exist_ok=True)

try:
    app.mount("/output", StaticFiles(directory=str(output_dir)), name="output")
except Exception as e:
    logger.warning(f"Could not mount output directory: {e}")

# Include routers
app.include_router(story.router)
app.include_router(stories.router)  # Dashboard & story management
app.include_router(tts.router)
app.include_router(voice.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "VoiceClone API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "voiceclone-api"
    }


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting VoiceClone API server...")
    logger.info("API documentation available at: http://localhost:8000/docs")
    logger.info("Frontend should be running at: http://localhost:3000")

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
