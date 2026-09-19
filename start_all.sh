#!/bin/bash
# Ένα κλικ για δικό σου PC: server + tunnel + bot
cd "$(dirname "$0")"
[ -f .env ] && set -a && source .env && set +a
python3 server.py &
SRV=$!
sleep 2
echo "Game: http://127.0.0.1:${PORT:-8000}/"
echo "Για Telegram Play χρειάζεσαι https tunnel (π.χ. cloudflared):"
echo "  cloudflared tunnel --url http://127.0.0.1:${PORT:-8000}"
echo "Μετά βάλε το https URL στο .env -> WEBAPP_URL, τρέξε:"
echo "  python3 tools/setup_bot.py"
echo "  python3 bot.py"
wait $SRV
