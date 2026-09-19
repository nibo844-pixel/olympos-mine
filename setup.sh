#!/bin/bash
cd "$(dirname "$0")"
if [ ! -f .env ]; then cp .env.example .env; echo "✓ Δημιούργησα .env (mock mode, δεν χρειάζεται τίποτα)"; fi
# φτιάξε manifest με σωστό URL
URL=$(grep WEBAPP_URL .env | cut -d= -f2 | tr -d '\r' | sed 's:/*$::')
[ -z "$URL" ] && URL="http://127.0.0.1:8000"
cat > web/tonconnect-manifest.json << JSONEOF
{"url": "$URL/", "name": "Olympos Mine", "iconUrl": "$URL/favicon.ico"}
JSONEOF
echo "✓ Manifest: $URL/"
echo ""
echo "Τρέξε: ./run.sh  και άνοιξε $URL/"
echo "Για Telegram live, βάλε στο .env BOT_TOKEN + WEBAPP_URL (https) + TON_WALLET και τρέξε: python3 tools/setup_bot.py"
