#!/usr/bin/env bash
# Render start script
set -o errexit

# Render already sets working dir to /opt/render/project/src/
# So we're already in the right place - just run uvicorn
exec python -m uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
