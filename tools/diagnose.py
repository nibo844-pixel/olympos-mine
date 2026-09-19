"""Διάγνωση Olympos Mine (stdlib). Δείχνει τι φταίει χωρίς τεχνικά."""
import json, os, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
print("== Olympos Mine diagnose ==")
tok = config.BOT_TOKEN
print("1) BOT_TOKEN:", "OK (set)" if tok else "MISSING")
if tok:
    try:
        req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/getMe")
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read().decode())
        print("2) Bot:", d.get("result", {}).get("username"), "| live: YES")
    except Exception as e:
        print("2) Bot: FAIL", e)
print("3) WEBAPP_URL:", config.WEBAPP_URL)
# check URL reachable + https?
u = config.WEBAPP_URL
if not u.startswith("https://"):
    print("4) URL check: FAIL — το Telegram θέλει https, όχι http")
else:
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            print("4) URL check: OK", r.status)
    except Exception as e:
        print("4) URL check: FAIL — νεκρό link (tunnel/server κλειστό):", str(e)[:120])
# local server files
import os as _os
print("5) Frontend:", "OK" if _os.path.isfile("web/index.html") else "MISSING")
print("6) Bot polling here:", "NO (τρέξε python3 bot.py σε δικό σου PC)")
