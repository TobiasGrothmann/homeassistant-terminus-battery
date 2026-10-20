#!/usr/bin/env bash
# Copy the integration to a Home Assistant OS box over SSH and restart Core.
#
# Requires the "Terminal & SSH" add-on with your public key and port 22 open.
#   HA_SSH_HOST=root@homeassistant.local HA_SSH_PORT=22 scripts/deploy.sh
set -euo pipefail

HOST="${HA_SSH_HOST:-root@homeassistant.local}"
PORT="${HA_SSH_PORT:-22}"
SRC="$(cd "$(dirname "$0")/.." && pwd)/custom_components/trmnl_terminus"
DEST="/config/custom_components/trmnl_terminus"

echo "→ ${HOST}:${DEST}"
ssh -p "$PORT" "$HOST" "mkdir -p /config/custom_components && rm -rf '$DEST'"
scp -r -P "$PORT" -q "$SRC" "$HOST:/config/custom_components/"
ssh -p "$PORT" "$HOST" "find '$DEST' -name '__pycache__' -type d -exec rm -rf {} + ; ha core restart"
echo "✓ deployed, Core restarting"
