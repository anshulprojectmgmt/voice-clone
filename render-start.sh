#!/usr/bin/env bash
# Render start script
set -o errexit

# Render sets working dir to /opt/render/project/src/
# The src code is in src/ subdirectory, so we use src.api.main:app
exec python -m uvicorn src.api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
