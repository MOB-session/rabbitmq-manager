#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "=== Stopping RabbitMQ 4.1.0 ==="

if command -v docker &> /dev/null; then
    if docker compose version &> /dev/null; then
        docker compose down
    else
        docker stop rabbitmq-server || true
        docker rm rabbitmq-server || true
    fi
    echo "[✓] RabbitMQ container stopped."
else
    echo "[!] Docker not found."
fi
