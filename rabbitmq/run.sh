#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "=== RabbitMQ 4.1.0 Quick Starter ==="

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    echo ""
    echo "[!] Docker is not installed on this system."
    echo "To install Docker on Ubuntu, run:"
    echo ""
    echo "    sudo apt update"
    echo "    sudo apt install -y docker.io docker-compose-v2"
    echo "    sudo usermod -aG docker \$USER"
    echo "    newgrp docker"
    echo ""
    echo "Then rerun: bash rabbitmq/run.sh"
    exit 1
fi

# Determine if sudo is needed for docker
DOCKER_CMD="docker"
if ! docker ps &> /dev/null; then
    if sudo -n docker ps &> /dev/null || [ "$EUID" -eq 0 ]; then
        DOCKER_CMD="sudo docker"
    else
        echo "[!] Need permissions for docker. Trying with sudo..."
        DOCKER_CMD="sudo docker"
    fi
fi

echo "[+] Starting RabbitMQ 4.1.0 container..."

# Try pulling the image first, handling DNS issues
if ! $DOCKER_CMD pull rabbitmq:4.1-management; then
    echo ""
    echo "[!] Docker failed to resolve Docker Hub (DNS i/o timeout on 127.0.0.53)."
    echo "Fixing Docker DNS by adding Google/Cloudflare DNS (8.8.8.8, 1.1.1.1)..."
    echo ""
    echo "Please run this command to configure Docker DNS:"
    echo "    sudo tee /etc/docker/daemon.json << 'EOF'"
    echo "{"
    echo '  "dns": ["8.8.8.8", "1.1.1.1"]'
    echo "}"
    echo "EOF"
    echo "    sudo systemctl restart docker"
    echo ""
    exit 1
fi

if $DOCKER_CMD compose version &> /dev/null; then
    $DOCKER_CMD compose up -d
else
    echo "[+] Running via direct 'docker run'..."
    $DOCKER_CMD run -d \
      --name rabbitmq-server \
      --restart unless-stopped \
      -p 5672:5672 \
      -p 15672:15672 \
      -e RABBITMQ_DEFAULT_USER=guest \
      -e RABBITMQ_DEFAULT_PASS=guest \
      -e RABBITMQ_DEFAULT_VHOST=/ \
      -v "$DIR/enabled_plugins":/etc/rabbitmq/enabled_plugins:ro \
      -v "$DIR/rabbitmq.conf":/etc/rabbitmq/rabbitmq.conf:ro \
      rabbitmq:4.1-management
fi

echo ""
echo "[✓] RabbitMQ 4.1.0 is starting!"
echo "    - AMQP Broker Port:       localhost:5672"
echo "    - Management Web UI:      http://localhost:15672"
echo "    - Credentials:            guest / guest"
echo ""
echo "To check logs: $DOCKER_CMD logs -f rabbitmq-server"
echo "To stop:       bash rabbitmq/stop.sh"
