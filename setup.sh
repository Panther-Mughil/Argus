#!/bin/bash
set -e

echo "Setting up Argus CTF Platform..."

# Create Python Virtual Environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    if command -v uv &> /dev/null; then
        uv venv -p 3.12 venv
    else
        python3 -m venv venv
    fi
fi

echo "Installing Python dependencies..."
source venv/bin/activate

if command -v uv &> /dev/null; then
    uv pip install -r requirements.txt
else
    pip install -r requirements.txt
fi

echo "Starting PostgreSQL container..."
# Use podman or docker to run postgres container directly
if command -v podman &> /dev/null; then
    CONTAINER_BIN="podman"
elif command -v docker &> /dev/null; then
    CONTAINER_BIN="docker"
else
    echo "Error: Neither podman nor docker found. Please install one of them to run the database."
    exit 1
fi

$CONTAINER_BIN run -d \
    --name argus-db \
    -e POSTGRES_USER=argus \
    -e POSTGRES_PASSWORD=argus_password \
    -e POSTGRES_DB=argus_db \
    -p 5432:5432 \
    -v argus_postgres_data:/var/lib/postgresql/data \
    docker.io/library/postgres:15-alpine

echo "Argus setup complete."
