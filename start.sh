#!/bin/bash
# Render startup script

# Set PYTHONPATH to current directory so 'src' package is found
export PYTHONPATH="${PWD}:${PYTHONPATH}"

# Run uvicorn from root directory using full module path
exec python -m uvicorn src.api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
