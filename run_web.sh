#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

echo "=== Starting RabbitMQ Web Manager on http://localhost:5000 ==="
python3 app.py
