#!/bin/bash
cd "$(dirname "$0")"
if [ -f .env ]; then set -a; source .env; set +a; fi
export PORT="${PORT:-8000}" HOST="${HOST:-127.0.0.1}"
echo "Olympos Mine -> http://$HOST:$PORT/"
python3 server.py
