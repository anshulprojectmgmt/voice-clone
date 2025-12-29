#!/bin/bash
# Render startup script

# Get the script directory (project root)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Set PYTHONPATH to include src directory
export PYTHONPATH="${SCRIPT_DIR}/src:${PYTHONPATH}"

# Change to project root
cd "${SCRIPT_DIR}" || exit 1

# Run uvicorn from project root with proper module path
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
