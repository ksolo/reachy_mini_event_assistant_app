#!/usr/bin/env bash
# setup_raspberry_pi.sh
#
# Installs system dependencies required by reachy_mini_event_assistant_app
# that are NOT part of the standard Reachy Mini OS image.
#
# The base Reachy OS image is expected to already provide:
#   Python 3, OpenCV, GStreamer, PyGObject, audio libraries, git, build tools.
#
# Run once after deploying the app to the robot:
#   chmod +x scripts/setup_raspberry_pi.sh
#   ./scripts/setup_raspberry_pi.sh

set -euo pipefail

echo "==> Installing app-specific system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y \
    libzbar0   # QR code scanning (pyzbar)

echo ""
echo "==> Checking for uv..."
if command -v uv &>/dev/null; then
    echo "    uv already installed: $(uv --version)"
else
    echo "    Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    echo "    uv installed: $(uv --version)"
fi

echo ""
echo "==> Done. Next steps:"
echo "    cd reachy_mini_event_assistant_app"
echo "    uv sync"
echo "    cp .env.example .env   # then fill in your API keys"
