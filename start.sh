#!/bin/bash
set -e

echo "Starting Argus Backend..."
# shellcheck disable=SC1091
source venv/bin/activate

if command -v podman &> /dev/null; then
    CONTAINER_BIN="podman"
elif command -v docker &> /dev/null; then
    CONTAINER_BIN="docker"
else
    echo "Error: Neither podman nor docker found."
    exit 1
fi

echo "Starting PostgreSQL container..."
$CONTAINER_BIN start argus-db

echo "PostgreSQL is running."

echo "Building frontend..."
if [ -d "frontend" ]; then
    (cd frontend && npm install --silent 2>/dev/null; npm run build)
fi

echo "Starting FastAPI Backend..."
# Run uvicorn on port 8000 (--reload picks up backend changes)
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
