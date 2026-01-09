"""
VoiceClone FastAPI Backend
Main application entry point
"""
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging
import os
from datetime import datetime

from .routes import story, tts, voice, stories, auth
from ..database.connection import init_db
from ..database.init_default_voice import init_default_voice

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
app.include_router(auth.router)  # Authentication routes
app.include_router(story.router)
app.include_router(stories.router)  # Dashboard & story management
app.include_router(tts.router)
app.include_router(voice.router)


@app.on_event("startup")
async def startup_event():
    """
    Application startup event handler

    Initializes:
    1. Database schema (creates tables if not exist)
    2. Default voice pre-caching (only if not using RunPod - eliminates 400-1100ms overhead on first use)
    """
    logger.info("=" * 60)
    logger.info("Application Startup")
    logger.info("=" * 60)

    # Initialize database
    logger.info("Initializing database...")
    try:
        init_db()
        logger.info("✓ Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

    # Pre-cache default voice (skip on Vercel/serverless platforms using RunPod)
    use_runpod = os.getenv("USE_RUNPOD", "false").lower() in ("true", "1", "yes")

    if use_runpod:
        logger.info("Using RunPod for TTS - skipping local model initialization")
    else:
        logger.info("Pre-caching default voice (this improves first TTS request by 10-20x)...")
        try:
            voice = init_default_voice()
            if voice:
                logger.info("✓ Default voice pre-cached successfully")
            else:
                logger.warning("! Default voice not initialized (will be cached on first use)")
        except Exception as e:
            logger.error(f"Failed to pre-cache default voice: {e}")
            logger.warning("  TTS will still work, but first request will be slower")

    logger.info("=" * 60)
    logger.info("Startup complete - Ready to accept requests")
    logger.info("=" * 60)


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
    """
    Health check endpoint

    Used by Render/monitoring services and frontend keep-alive polling
    """
    return {
        "status": "healthy",
        "service": "voiceclone-api",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/ping")
async def ping():
    """
    Lightweight keep-alive endpoint for Render inactivity prevention

    Frontend polls this every 30-40 seconds during long operations
    to prevent Render from shutting down due to inactivity.
    """
    return {"pong": True}


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
