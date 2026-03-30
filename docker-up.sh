#!/usr/bin/env bash
set -e

# Build and start all services
cd "$(dirname "$0")"
docker compose up --build -d

# Restart nginx after web is up to avoid stale upstream state
sleep 2
docker compose restart nginx

echo "Docker stack is up and nginx has been restarted."
