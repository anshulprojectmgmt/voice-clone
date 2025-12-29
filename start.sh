#!/bin/bash
# Render startup script

# Get the script directory (project root)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Add src directory to PYTHONPATH so Python can find the api module
export PYTHONPATH="${SCRIPT_DIR}/src:${PYTHONPATH}"

# Run uvicorn from the project root
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
