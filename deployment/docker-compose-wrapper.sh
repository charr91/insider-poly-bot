#!/bin/bash
# Docker Compose wrapper - automatically detects and uses available version

# Try docker compose (v2 plugin) first
if docker compose version &>/dev/null; then
    docker compose "$@"
# Fall back to docker-compose (v1 standalone)
elif command -v docker-compose &>/dev/null; then
    docker-compose "$@"
else
    echo "Error: Neither 'docker compose' nor 'docker-compose' is available"
    exit 1
fi
