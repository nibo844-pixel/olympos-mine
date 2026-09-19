"""One-click Telegram setup (stdlib). Βάζει commands + menu button. Θέλει BOT_TOKEN."""
import json, os, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
tok = config.BOT_TOKEN
url = config.WEBAPP_URL.rstrip("/") + "/"
if not tok:
    print("Δεν βρήκα BOT_TOKEN.")
    print("1) BotFather -> /newbot -> πάρε token")
    print("2) Βάλτο στο .env σαν BOT_TOKEN=123:ABC")
    print("3) Ξανατρέξε: python3 tools/setup_bot.py")
    sys.exit(1)
def call(m, d):
    req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/{m}",
        data=json.dumps(d).encode(), headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())
print("URL:", url)
print("setMyCommands:", call("setMyCommands", {"commands":[
    {"command":"start","description":"Ξεκίνα το mining"},
    {"command":"play","description":"Παίξε Olympos Mine"}]}) .get("ok"))
try:
    print("menuButton:", call("setChatMenuButton", {"menu_button":{"type":"web_app","text":"⛏️ Play","web_app":{"url":url}}}).get("ok"))
except Exception as e:
    print("menuButton skip:", e)
print("✓ Done. Στείλε /start στο bot σου.")
