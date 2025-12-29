#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Production startup script for Render deployment
"""
import os
import sys
from pathlib import Path

# Add src to Python path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

# Get port from environment (Render provides this)
PORT = int(os.getenv("PORT", 8000))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,  # No reload in production
        log_level="info"
    )
