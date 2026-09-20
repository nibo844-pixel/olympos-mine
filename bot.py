"""Telegram bot (stdlib only). Stars payments + Play button."""
import json
import os
import time
import sqlite3
import urllib.request
import urllib.parse
import config

TOKEN = os.environ.get("BOT_TOKEN", config.BOT_TOKEN)
WEBAPP_URL = os.environ.get("WEBAPP_URL", config.WEBAPP_URL)

def api(method, data=None):
    if not TOKEN:
        raise RuntimeError("Missing BOT_TOKEN")
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    body = json.dumps(data or {}).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())

def grant(uid, product, tx=""):
    import server
    c = server.db()
    try:
        return server.grant_product(c, uid, product, "stars", tx)
    finally:
        c.close()

GROUP_URL = "https://t.me/aetagent"

def send_start(chat_id, referrer=""):
    url = WEBAPP_URL
    if referrer:
        url += ("&" if "?" in url else "?") + "ref=" + urllib.parse.quote(referrer)
    kb = {"inline_keyboard": [
        [{"text": "⛏️ Παίξε Olympos Mine", "web_app": {"url": url}}],
        [{"text": "💬 Μπες στο γκρουπ Myth", "url": GROUP_URL}],
    ]}
    api("sendMessage", {"chat_id": chat_id,
        "text": "🏛️ Olympos Mine!\n\nΣκάψε $MYTH • Διάλεξε Πόλη • Κέρδισε στο τουρνουά.\n\n⚡ x5 κεραυνός • 🔮 χρησμός • 👥 φέρε φίλους = 10% για πάντα\n💬 Νέα + δώρα στο γκρουπ: @aetagent",
        "reply_markup": kb})

def send_welcome(chat_id, name=""):
    url = WEBAPP_URL
    kb = {"inline_keyboard": [
        [{"text": "⛏️ Παίξε τώρα", "web_app": {"url": url}}],
        [{"text": "💬 Γκρουπ Myth", "url": GROUP_URL}],
    ]}
    api("sendMessage", {"chat_id": chat_id,
        "text": f"Καλώς ήρθες {name}! 🏛️\nΠάτα Παίξε, διάλεξε πόλη (Αθήνα/Σπάρτη/Κρήτη) και σκάψε $MYTH.\n💬 Για βοήθεια μπες @aetagent",
        "reply_markup": kb})

def main():
    if not TOKEN:
        print("Βάλε BOT_TOKEN:  export BOT_TOKEN=123:ABC")
        print(f"WEBAPP_URL={WEBAPP_URL}")
        print("Stars + webhook δουλεύουν και σε mock mode τοπικά (mock_claim).")
        return
    print("Bot polling (Stars enabled)...")
    off = 0
    while True:
        try:
            res = api("getUpdates", {"offset": off, "timeout": 25})
            for up in res.get("result", []):
                off = up["update_id"] + 1
                if "pre_checkout_query" in up:
                    q = up["pre_checkout_query"]
                    api("answerPreCheckoutQuery", {"pre_checkout_query_id": q["id"], "ok": True})
                    continue
                msg = up.get("message", {})
                if "successful_payment" in msg:
                    sp = msg["successful_payment"]
                    try:
                        pl = json.loads(sp.get("invoice_payload", "{}"))
                        grant(pl.get("uid", ""), pl.get("product", ""), sp.get("telegram_payment_charge_id", ""))
                    except Exception as e:
                        print("grant err:", e)
                    api("sendMessage", {"chat_id": msg["chat"]["id"], "text": "✅ Πληρωμή OK! Το boost μπήκε στο παιχνίδι."})
                    continue
                new_members = msg.get("new_chat_members")
                if new_members:
                    for m in new_members:
                        try:
                            send_welcome(msg["chat"]["id"], "@" + m.get("username", "") if m.get("username") else m.get("first_name", ""))
                        except Exception:
                            pass
                    continue
                if "text" in msg:
                    chat = msg["chat"]["id"]
                    uid = str(msg["from"]["id"])
                    txt = msg["text"]
                    if txt.startswith("/start"):
                        parts = txt.split()
                        ref = parts[1] if len(parts) > 1 else ""
                        send_start(chat, ref if ref != uid else "")
                    elif txt.startswith("/play") or txt.startswith("/help"):
                        send_start(chat)
        except Exception as e:
            print("retry:", e)
            time.sleep(3)

if __name__ == "__main__":
    main()
