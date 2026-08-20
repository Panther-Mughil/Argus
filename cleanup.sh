#!/bin/bash
echo "Cleaning up Argus..."

if command -v podman &> /dev/null; then
    CONTAINER_BIN="podman"
elif command -v docker &> /dev/null; then
    CONTAINER_BIN="docker"
else
    echo "Error: Neither podman nor docker found."
    exit 1
fi

$CONTAINER_BIN stop argus-db || true
$CONTAINER_BIN rm -v argus-db || true

echo "Argus cleanup complete. Database volumes have been removed."
