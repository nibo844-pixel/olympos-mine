"""Olympos Mine backend - stdlib only (http.server + sqlite3)."""
import json
import os
import sqlite3
import time
import random
import unicodedata
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import config

RATE = {}
PG = bool(__import__('os').environ.get("DATABASE_URL", ""))
if PG:
    import psycopg2
    import psycopg2.extras

class DB:
    def __init__(self, conn, pg):
        self.conn = conn
        self.pg = pg
    def execute(self, sql, params=()):
        if self.pg:
            sql = sql.replace("?", "%s")
            cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql, params)
            return cur
        return self.conn.execute(sql, params)
    def commit(self):
        return self.conn.commit()
    def rollback(self):
        try:
            self.conn.rollback()
        except Exception:
            pass
    def close(self):
        try:
            if getattr(self, "pooled", False) and _PGPOOL is not None:
                _PGPOOL.putconn(self.conn)
                return
            return self.conn.close()
        except Exception:
            pass

def _row(r):
    return None if r is None else dict(r)

_PGPOOL = None
_INIT_DONE = False

def db():
    global _PGPOOL, _INIT_DONE
    if PG:
        if _PGPOOL is None:
            from psycopg2 import pool as _pgpool
            _PGPOOL = _pgpool.ThreadedConnectionPool(1, 12, os.environ["DATABASE_URL"])
        c = DB(_PGPOOL.getconn(), True)
        c.pooled = True
        if not _INIT_DONE:
            _init(c)
            _INIT_DONE = True
        return c
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    _sq = sqlite3.connect(config.DB_PATH)
    _sq.row_factory = sqlite3.Row
    c = DB(_sq, False)
    if not _INIT_DONE:
        _init(c)
        _INIT_DONE = True
    return c

_CACHE = {}

def cached(key, ttl, fn):
    now = time.time()
    if key in _CACHE and now - _CACHE[key][0] < ttl:
        return _CACHE[key][1]
    val = fn()
    _CACHE[key] = (now, val)
    return val

DDL_QUESTS = "CREATE TABLE IF NOT EXISTS quests(user_id TEXT, code TEXT, claimed INTEGER DEFAULT 0, PRIMARY KEY(user_id, code))"
DDL_META = "CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)"

def _init(c):
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        user_id TEXT PRIMARY KEY, username TEXT DEFAULT '',
        myth REAL DEFAULT 0, energy REAL DEFAULT 1000,
        polis TEXT DEFAULT 'athens', rigs TEXT DEFAULT '{}',
        referrer TEXT DEFAULT '', last_seen INTEGER DEFAULT 0,
        last_claim INTEGER DEFAULT 0, last_raid INTEGER DEFAULT 0,
        oracle_day TEXT DEFAULT '', streak INTEGER DEFAULT 0,
        created INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS purchases(
        id SERIAL PRIMARY KEY, user_id TEXT, product TEXT,
        source TEXT DEFAULT '', tx TEXT DEFAULT '', created INTEGER)""") if c.pg else c.execute("""CREATE TABLE IF NOT EXISTS purchases(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, product TEXT,
        source TEXT DEFAULT '', tx TEXT DEFAULT '', created INTEGER)""")
    c.execute("CREATE TABLE IF NOT EXISTS wallets(user_id TEXT PRIMARY KEY, ton_address TEXT, updated INTEGER)")
    for col, ddl in [("shield_until","INTEGER DEFAULT 0"),("turbo","INTEGER DEFAULT 0"),
                     ("ton_wallet","TEXT DEFAULT ''"),("premium","INTEGER DEFAULT 0"),
                     ("taps_total","INTEGER DEFAULT 0"),("last_daily","INTEGER DEFAULT 0"),
                     ("daily_streak","INTEGER DEFAULT 0"),("last_ad","INTEGER DEFAULT 0"),
                     ("ads_day","TEXT DEFAULT ''"),("ads_n","INTEGER DEFAULT 0"),
                     ("total_earned","REAL DEFAULT 0"),("ref_earned","REAL DEFAULT 0")]:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {ddl}")
            c.commit()
        except Exception:
            c.rollback()
    c.execute(DDL_QUESTS)
    c.execute(DDL_META)
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_users_myth ON users(myth DESC)")
    except Exception:
        c.rollback()
    try:
        c.execute("UPDATE users SET total_earned=myth WHERE myth>COALESCE(total_earned,0)")
    except Exception:
        c.rollback()
    c.commit()
    return c

def norm(s):
    s = (s or "").strip().lower()
    s = "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")
    return s.replace(" ", "")

def rigs_dict(row):
    try:
        d = json.loads(row["rigs"] or "{}")
    except Exception:
        d = {}
    return {k: int(d.get(k, 0)) for k in config.RIGS}

def per_sec(rigs, turbo=0, premium=0):
    base = sum(rigs.get(k, 0) * config.RIGS[k]["per_sec"] for k in config.RIGS)
    return base + (turbo or 0) * config.PREMIUM_RIG_PER_SEC + (premium or 0) * config.PREMIUM_RIG_PER_SEC

def tg_bot_call(method, data):
    import urllib.request
    token = config.BOT_TOKEN
    if not token:
        return {"ok": False, "mock": True}
    try:
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/{method}",
            data=json.dumps(data).encode(), headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"ok": False, "error": str(e)}

def verify_ton_payment(tx_hash, uid, user_wallet=""):
    """Real check via toncenter when TON_WALLET is set, else demo mode.
    Returns (ok:bool, info:str)."""
    import urllib.request, urllib.parse
    to_wallet = (config.TON_WALLET or "").strip()
    tx = (tx_hash or "").strip()
    if not to_wallet:
        return True, "demo (no TON_WALLET set)"
    if tx.startswith("mock_") or tx == "":
        return False, "Στείλε πρώτα τα TON και βάλε το tx hash"
    need = int(config.TON_PREMIUM_PRICE * 1e9)
    try:
        q = {"address": to_wallet, "limit": 30, "archival": "false"}
        if config.TON_API_KEY:
            q["api_key"] = config.TON_API_KEY
        url = "https://toncenter.com/api/v2/getTransactions?" + urllib.parse.urlencode(q)
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read().decode())
        txs = data.get("result", [])
        for t in txs:
            h = t.get("transaction_id", {}).get("hash", "")
            in_msg = t.get("in_msg", {}) or {}
            val = int(in_msg.get("value", "0") or 0)
            src = in_msg.get("source", "") or ""
            comment = str(in_msg.get("message", "") or in_msg.get("body", "") or "")
            if h and h != tx and tx not in h and h not in tx:
                # allow match by comment==uid too
                if uid not in comment and (not user_wallet or user_wallet not in src):
                    continue
            if val >= need:
                if uid in comment or (user_wallet and user_wallet in src) or h == tx or tx in h or h in tx:
                    return True, f"found {val/1e9:.3f} TON"
        # fallback: if toncenter reachable but tx not found yet, explain
        return False, "Δεν βρήκα πληρωμή. Περίμενε 1-2 λεπτά και ξαναπάτα Verify (comment=user_id)."
    except Exception as e:
        return False, "Δεν επιβεβαιώθηκε στο TON (έλεγξε TON_WALLET / δοκίμασε σε 1-2 λεπτά)."

def grant_product(c, uid, product, source="mock", tx=""):
    now = int(time.time())
    u = _row(c.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone())
    if not u:
        return False
    if product == "energy_full":
        c.execute("UPDATE users SET energy=? WHERE user_id=?", (config.ENERGY_MAX, uid))
    elif product == "shield_7d":
        until = max(now, u["shield_until"] or 0) + 7*86400
        c.execute("UPDATE users SET shield_until=? WHERE user_id=?", (until, uid))
    elif product == "turbo_rig":
        c.execute("UPDATE users SET turbo=COALESCE(turbo,0)+1 WHERE user_id=?", (uid,))
    elif product == "ton_premium":
        c.execute("UPDATE users SET premium=COALESCE(premium,0)+1 WHERE user_id=?", (uid,))
    else:
        return False
    c.execute("INSERT INTO purchases(user_id,product,source,tx,created) VALUES(?,?,?,?,?)",
              (uid, product, source, tx, now))
    c.commit()
    return True

def touch(row, c, now):
    rigs = rigs_dict(row)
    rate = per_sec(rigs, row["turbo"] if "turbo" in row.keys() else 0, row["premium"] if "premium" in row.keys() else 0)
    last_claim = row["last_claim"] or now
    dt = max(0, min(now - last_claim, config.OFFLINE_CAP_SEC))
    earn = rate * dt
    energy = min(config.ENERGY_MAX, (row["energy"] or 0) + max(0, now - (row["last_seen"] or now)) * config.ENERGY_REGEN_PER_SEC)
    myth = (row["myth"] or 0) + earn
    c.execute("UPDATE users SET myth=?, energy=?, last_seen=?, last_claim=?, total_earned=COALESCE(total_earned,0)+? WHERE user_id=?",
              (myth, energy, now, now, earn, row["user_id"]))
    c.commit()
    return myth, energy, rigs, rate

def get_user(c, uid):
    r = c.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
    return _row(r)

def payload(u, rigs, rate):
    k = u.keys()
    return {"user_id": u["user_id"], "username": u["username"], "myth": round(u["myth"], 1),
            "energy": int(u["energy"]), "energy_max": config.ENERGY_MAX,
            "polis": u["polis"], "rigs": rigs, "rate": rate, "streak": u["streak"],
            "turbo": u["turbo"] if "turbo" in k else 0,
            "premium": u["premium"] if "premium" in k else 0,
            "shield_until": u["shield_until"] if "shield_until" in k else 0,
            "ton_wallet": u["ton_wallet"] if "ton_wallet" in k else "",
            "total_earned": round(u["total_earned"] or 0, 1) if "total_earned" in k else 0,
            "ref_earned": round(u["ref_earned"] or 0, 1) if "ref_earned" in k else 0}

def ensure_extra(c):
    try:
        c.execute(DDL_QUESTS)
        c.execute(DDL_META)
        c.commit()
    except Exception:
        try:
            c.rollback()
        except Exception:
            pass

def meta_get(c, k):
    ensure_extra(c)
    r = _row(c.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone())
    return r["v"] if r else None

def meta_set(c, k, v):
    v = str(v)
    if c.pg:
        c.execute("INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=EXCLUDED.v", (k, v))
    else:
        c.execute("INSERT OR REPLACE INTO meta(k,v) VALUES(?,?)", (k, v))
    c.commit()

def quest_progress(u, rigs):
    out = []
    for q in config.QUESTS:
        code = q["code"]
        if code == "tap100":
            have = int(u.get("taps_total", 0) or 0)
        elif code == "rig3":
            have = sum(int(v) for v in (rigs or {}).values())
        elif code == "oracle1":
            have = 1 if u.get("oracle_day") else 0
        elif code == "raid1":
            have = 1 if (u.get("last_raid", 0) or 0) > 0 else 0
        else:
            have = 0
        out.append({"code": code, "need": q["need"], "have": have, "reward": q["reward"]})
    return out

def quest_claimed(c, uid):
    ensure_extra(c)
    rows = c.execute("SELECT code FROM quests WHERE user_id=? AND claimed=1", (uid,)).fetchall()
    return set(_row(r)["code"] for r in rows)

def check_rate(uid, min_interval=0.4):
    now = time.time()
    last = RATE.get(uid, 0)
    if now - last < min_interval:
        return False
    RATE[uid] = now
    return True

class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "OlymposMine/1.0"

    def log_message(self, *a):
        pass

    def send_json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def read_json(self):
        try:
            n = int(self.headers.get("Content-Length", 0) or 0)
        except Exception:
            n = 0
        if n <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:
            return {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        p = urlparse(self.path)
        if p.path.startswith("/api/"):
            return self.api_get(p)
        # static
        base = os.path.join(config.BASE_DIR, "web")
        rel = p.path if p.path != "/" else "/index.html"
        rel = rel.split("?")[0].lstrip("/")
        fp = os.path.normpath(os.path.join(base, rel))
        if not fp.startswith(base) or not os.path.isfile(fp):
            fp = os.path.join(base, "index.html")
            if not os.path.isfile(fp):
                return self.send_json({"ok": False, "error": "no frontend yet"}, 404)
        ext = os.path.splitext(fp)[1].lower()
        ct = {".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css", ".json": "application/json"}.get(ext, "application/octet-stream")
        try:
            with open(fp, "rb") as f:
                b = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        except Exception as e:
            self.send_json({"ok": False, "error": str(e)}, 500)

    def api_get(self, p):
        c = db()
        now = int(time.time())
        try:
            if p.path == "/api/state":
                q = parse_qs(p.query)
                uid = (q.get("user_id", [""])[0] or "").strip()[:64]
                if not uid:
                    return self.send_json({"ok": False, "error": "need user_id"})
                u = get_user(c, uid)
                if not u:
                    return self.send_json({"ok": False, "error": "need init"})
                myth, energy, rigs, rate = touch(u, c, now)
                u = get_user(c, uid)
                day = time.strftime("%Y-%m-%d")
                oi = (now // 86400) % len(config.ORACLES)
                return self.send_json({"ok": True, "state": payload(u, rigs, rate),
                    "oracle": {"q": config.ORACLES[oi]["q"], "done": u["oracle_day"] == day},
                    "rigs_catalog": config.RIGS})
            if p.path == "/api/leaderboard":
                def _board():
                    rows = c.execute("SELECT user_id, username, myth, polis FROM users ORDER BY myth DESC LIMIT 20").fetchall()
                    return {"ok": True, "top": [_row(r) for r in rows]}
                return self.send_json(cached("board", 15, _board))
            if p.path == "/api/shop/catalog":
                return self.send_json({"ok": True, "stars": config.STARS_PRODUCTS,
                    "ton": {"price": config.TON_PREMIUM_PRICE, "to": config.TON_WALLET,
                            "per_sec": config.PREMIUM_RIG_PER_SEC},
                    "adsgram": config.ADSGRAM_BLOCK_ID})
            if p.path == "/api/season":
                def _season():
                    rows = [_row(r) for r in c.execute("SELECT polis, SUM(myth) s, COUNT(*) n FROM users GROUP BY polis").fetchall()]
                    by = {r["polis"]: {"myth": round(float(r["s"] or 0)), "players": r["n"]} for r in rows}
                    for pol in config.POLIS_LIST:
                        by.setdefault(pol, {"myth": 0, "players": 0})
                    week = now // (7 * 86400)
                    ends = (week + 1) * 7 * 86400 - now
                    leader = max(config.POLIS_LIST, key=lambda k: by[k]["myth"])
                    lastw = None
                    try:
                        paid = meta_get(c, "season_paid_week")
                        if paid is not None and paid != str(week):
                            top = [_row(r) for r in c.execute(
                                "SELECT user_id, username, myth FROM users WHERE polis=? ORDER BY myth DESC LIMIT 3",
                                (leader,)).fetchall()]
                            winners = []
                            for i, w in enumerate(top):
                                prize = config.TOURNAMENT_PRIZES[i] if i < len(config.TOURNAMENT_PRIZES) else 0
                                if prize:
                                    c.execute("UPDATE users SET myth=myth+?, total_earned=COALESCE(total_earned,0)+? WHERE user_id=?", (prize, prize, w["user_id"]))
                                winners.append({"username": w["username"] or w["user_id"], "prize": prize})
                            meta_set(c, "season_paid_week", week)
                            meta_set(c, "season_winners", json.dumps({"week": int(paid), "polis": leader, "winners": winners}))
                            c.commit()
                        elif paid is None:
                            meta_set(c, "season_paid_week", week)
                        try:
                            lastw = json.loads(meta_get(c, "season_winners") or "null")
                        except Exception:
                            lastw = None
                    except Exception as e:
                        return {"ok": False, "error": "dbg:" + repr(e)}
                    return {"ok": True, "polis": by, "ends_in_sec": ends, "leader": leader,
                            "names": config.POLIS_NAMES, "week": week,
                            "prizes": config.TOURNAMENT_PRIZES, "winners": lastw}
                return self.send_json(cached("season", 20, _season))
            return self.send_json({"ok": False, "error": "unknown"}, 404)
        finally:
            c.close()

    def do_POST(self):
        p = urlparse(self.path).path
        c = db()
        now = int(time.time())
        try:
            data = self.read_json()
            if p == "/webhook":
                upd = data
                msg0 = upd.get("message", {})
                txt0 = str(msg0.get("text", "") or "")
                if txt0.startswith("/start") or txt0.startswith("/play"):
                    try:
                        chat = msg0["chat"]["id"]
                        uid = str(msg0.get("from", {}).get("id", ""))
                        parts = txt0.split()
                        ref = parts[1] if len(parts) > 1 else ""
                        url = config.WEBAPP_URL.rstrip("/") + "/"
                        if ref and ref != uid:
                            import urllib.parse as _up
                            url += ("&" if "?" in url else "?") + "ref=" + _up.quote(ref)
                        tg_bot_call("sendMessage", {"chat_id": chat,
                            "text": "🏛️ Olympos Mine!\n\nΣκάψε $MYTH, πάρε Stars boosts και TON premium rigs.\n\n⚡ x5 κεραυνός • 🔮 χρησμός +500 • 👥 referral 10%",
                            "reply_markup": {"inline_keyboard": [[{"text": "⛏️ Παίξε Olympos Mine", "web_app": {"url": url}}]]}})
                    except Exception:
                        pass
                    return self.send_json({"ok": True})
                if "pre_checkout_query" in upd:
                    tg_bot_call("answerPreCheckoutQuery", {"pre_checkout_query_id": upd["pre_checkout_query"]["id"], "ok": True})
                    return self.send_json({"ok": True})
                msg = upd.get("message", {})
                sp = msg.get("successful_payment")
                if sp:
                    try:
                        pl = json.loads(sp.get("invoice_payload", "{}"))
                        grant_product(c, pl.get("uid", ""), pl.get("product", ""), "stars", sp.get("telegram_payment_charge_id", ""))
                    except Exception:
                        pass
                    return self.send_json({"ok": True})
                return self.send_json({"ok": True})
            if p == "/api/init":
                uid = str(data.get("user_id", "") or "").strip()[:64]
                if not uid:
                    return self.send_json({"ok": False, "error": "need user_id"}, 400)
                username = str(data.get("username", "") or "")[:64]
                polis = str(data.get("polis", "") or "athens")
                if polis not in config.POLIS_LIST:
                    polis = "athens"
                referrer = str(data.get("referrer", "") or "").strip()[:64]
                u = get_user(c, uid)
                if not u:
                    if referrer and referrer != uid and get_user(c, referrer):
                        try:
                            c.execute("UPDATE users SET myth=myth+100 WHERE user_id=?", (referrer,))
                        except Exception:
                            pass
                    else:
                        referrer = ""
                    c.execute("INSERT INTO users(user_id,username,myth,energy,polis,rigs,referrer,last_seen,last_claim,created) VALUES(?,?,?,?,?,?,?,?,?,?)",
                              (uid, username, 0, config.ENERGY_MAX, polis, "{}", referrer, now, now, now))
                    c.commit()
                    u = get_user(c, uid)
                else:
                    c.execute("UPDATE users SET username=?, last_seen=? WHERE user_id=?", (username or u["username"], now, uid))
                    c.commit()
                    u = get_user(c, uid)
                myth, energy, rigs, rate = touch(u, c, now)
                u = get_user(c, uid)
                return self.send_json({"ok": True, "state": payload(u, rigs, rate)})
            # all below need existing user
            uid = str(data.get("user_id", "") or "").strip()[:64]
            if not uid:
                return self.send_json({"ok": False, "error": "need user_id"}, 400)
            u = get_user(c, uid)
            if not u:
                return self.send_json({"ok": False, "error": "need init"}, 400)
            myth, energy, rigs, rate = touch(u, c, now)
            u = get_user(c, uid)

            if p == "/api/tap":
                if not check_rate(uid + ":tap", 0.2):
                    return self.send_json({"ok": False, "error": "too fast"}, 429)
                try:
                    taps = int(data.get("taps", 1))
                except Exception:
                    taps = 1
                taps = max(1, min(taps, config.TAP_MAX_PER_REQUEST))
                zeus = bool(data.get("zeus", False))
                if energy < taps:
                    return self.send_json({"ok": False, "error": "no energy", "energy": int(energy)}, 400)
                mult = config.ZEUS_MULTIPLIER if zeus else 1
                gain = taps * config.TAP_REWARD * mult
                energy -= taps
                myth = u["myth"] + gain
                c.execute("UPDATE users SET myth=?, energy=?, taps_total=COALESCE(taps_total,0)+?, total_earned=COALESCE(total_earned,0)+? WHERE user_id=?", (myth, energy, taps, gain, uid))
                if u["referrer"]:
                    try:
                        c.execute("UPDATE users SET myth=myth+?, total_earned=COALESCE(total_earned,0)+?, ref_earned=COALESCE(ref_earned,0)+? WHERE user_id=?", (gain * 0.1, gain * 0.1, gain * 0.1, u["referrer"]))
                    except Exception:
                        pass
                c.commit()
                return self.send_json({"ok": True, "gain": gain, "myth": round(myth, 1), "energy": int(energy)})
            if p == "/api/claim":
                u = get_user(c, uid)
                return self.send_json({"ok": True, "myth": round(u["myth"], 1), "rate": rate, "energy": int(u["energy"])})
            if p == "/api/buy":
                kind = str(data.get("rig", ""))
                if kind not in config.RIGS:
                    return self.send_json({"ok": False, "error": "bad rig"}, 400)
                cost = config.RIGS[kind]["cost"]
                owned = rigs.get(kind, 0)
                price = int(cost * (1.6 ** owned))
                if u["myth"] < price:
                    return self.send_json({"ok": False, "error": "need more MYTH"}, 400)
                rigs[kind] = owned + 1
                c.execute("UPDATE users SET myth=?, rigs=? WHERE user_id=?", (u["myth"] - price, json.dumps(rigs), uid))
                c.commit()
                return self.send_json({"ok": True, "rigs": rigs, "myth": round(u["myth"] - price, 1), "rate": per_sec(rigs, u["turbo"] if "turbo" in u.keys() else 0, u["premium"] if "premium" in u.keys() else 0)})
            if p == "/api/oracle":
                day = time.strftime("%Y-%m-%d")
                if u["oracle_day"] == day:
                    return self.send_json({"ok": False, "error": "done today"}, 400)
                oi = (now // 86400) % len(config.ORACLES)
                ans = norm(data.get("answer", ""))
                if ans and (ans in norm(config.ORACLES[oi]["a"]) or norm(config.ORACLES[oi]["a"]) in ans):
                    myth = u["myth"] + 500
                    c.execute("UPDATE users SET myth=?, oracle_day=?, streak=streak+1, total_earned=COALESCE(total_earned,0)+500 WHERE user_id=?", (myth, day, uid))
                    c.commit()
                    return self.send_json({"ok": True, "reward": 500, "myth": round(myth, 1)})
                return self.send_json({"ok": False, "error": "wrong"})
            if p == "/api/raid":
                if now - (u["last_raid"] or 0) < 20 * 3600:
                    return self.send_json({"ok": False, "error": "come back later"}, 400)
                loot = random.randint(50, 200)
                myth = u["myth"] + loot
                c.execute("UPDATE users SET myth=?, last_raid=?, total_earned=COALESCE(total_earned,0)+? WHERE user_id=?", (myth, now, loot, uid))
                c.commit()
                return self.send_json({"ok": True, "loot": loot, "myth": round(myth, 1)})
            if p == "/api/daily":
                last = int(u.get("last_daily", 0) or 0)
                wait = 20 * 3600 - (now - last)
                if wait > 0:
                    return self.send_json({"ok": False, "error": "wait", "wait_sec": wait,
                                           "streak": int(u.get("daily_streak", 0) or 0)}, 400)
                streak = int(u.get("daily_streak", 0) or 0) + 1 if (now - last) < 48 * 3600 else 1
                reward = config.DAILY_REWARDS[min(streak, 7)]
                c.execute("UPDATE users SET myth=myth+?, last_daily=?, daily_streak=?, total_earned=COALESCE(total_earned,0)+? WHERE user_id=?",
                          (reward, now, streak, reward, uid))
                c.commit()
                u = get_user(c, uid)
                return self.send_json({"ok": True, "reward": reward, "streak": streak,
                                       "myth": round(u["myth"], 1)})
            if p == "/api/quests":
                try:
                    prog = quest_progress(u, rigs)
                    claimed = quest_claimed(c, uid)
                except Exception as e:
                    return self.send_json({"ok": False, "error": "dbg:" + repr(e)}, 500)
                for q in prog:
                    q["claimed"] = q["code"] in claimed
                    q["done"] = q["have"] >= q["need"]
                return self.send_json({"ok": True, "quests": prog})
            if p == "/api/quest_claim":
                code = str(data.get("code", ""))
                prog = {q["code"]: q for q in quest_progress(u, rigs)}
                if code not in prog:
                    return self.send_json({"ok": False, "error": "bad quest"}, 400)
                if code in quest_claimed(c, uid):
                    return self.send_json({"ok": False, "error": "claimed"}, 400)
                if prog[code]["have"] < prog[code]["need"]:
                    return self.send_json({"ok": False, "error": "not done"}, 400)
                c.execute("UPDATE users SET myth=myth+?, total_earned=COALESCE(total_earned,0)+? WHERE user_id=?", (prog[code]["reward"], prog[code]["reward"], uid))
                if c.pg:
                    c.execute("INSERT INTO quests(user_id,code,claimed) VALUES(?,?,1) ON CONFLICT(user_id,code) DO UPDATE SET claimed=1", (uid, code))
                else:
                    c.execute("INSERT OR REPLACE INTO quests(user_id,code,claimed) VALUES(?,?,1)", (uid, code))
                c.commit()
                u = get_user(c, uid)
                return self.send_json({"ok": True, "reward": prog[code]["reward"], "myth": round(u["myth"], 1)})
            if p == "/api/ads/reward":
                day = time.strftime("%Y-%m-%d")
                n = int(u.get("ads_n", 0) or 0) if u.get("ads_day") == day else 0
                if now - int(u.get("last_ad", 0) or 0) < config.ADS_COOLDOWN_SEC:
                    return self.send_json({"ok": False, "error": "cooldown"}, 400)
                if n >= config.ADS_MAX_PER_DAY:
                    return self.send_json({"ok": False, "error": "limit"}, 400)
                energy = min(config.ENERGY_MAX, int(u["energy"] or 0) + config.ADS_REWARD_ENERGY)
                c.execute("UPDATE users SET energy=?, last_ad=?, ads_day=?, ads_n=? WHERE user_id=?",
                          (energy, now, day, n + 1, uid))
                c.commit()
                return self.send_json({"ok": True, "energy": energy, "left": config.ADS_MAX_PER_DAY - n - 1})
            if p == "/api/convert/preview":
                total = _row(c.execute("SELECT COALESCE(SUM(myth),0) s, COUNT(*) n FROM users").fetchone())
                tot = float(total["s"] or 0)
                mine = float(u["myth"] or 0)
                share = (mine / tot * 100) if tot > 0 else 0
                est = share / 100 * config.P2E_POOL
                cap = config.P2E_POOL * config.MAX_SHARE_PCT / 100
                return self.send_json({"ok": True, "mine": round(mine), "total": round(tot),
                    "players": total["n"], "pool": config.P2E_POOL, "share_pct": round(share, 4),
                    "estimate": round(min(est, cap)), "capped": est > cap,
                    "min_ok": mine >= config.MIN_POINTS})
            if p == "/api/shop/stars_order":
                prod = str(data.get("product", ""))
                if prod not in config.STARS_PRODUCTS:
                    return self.send_json({"ok": False, "error": "bad product"}, 400)
                info = config.STARS_PRODUCTS[prod]
                if not config.BOT_TOKEN:
                    return self.send_json({"ok": True, "mock": True,
                        "invoice_link": f"mock:stars:{prod}",
                        "hint": "Βάλε BOT_TOKEN για πραγματικές πληρωμές Stars"})
                r = tg_bot_call("createInvoiceLink", {
                    "title": info["title"], "description": info["desc"],
                    "payload": json.dumps({"uid": uid, "product": prod}),
                    "currency": "XTR", "prices": [{"label": info["title"], "amount": info["stars"]}]})
                if r.get("ok"):
                    return self.send_json({"ok": True, "invoice_link": r.get("result")})
                return self.send_json({"ok": False, "error": r.get("description", "telegram error")}, 400)
            if p == "/api/shop/mock_claim":
                prod = str(data.get("product", ""))
                if prod not in config.STARS_PRODUCTS:
                    return self.send_json({"ok": False, "error": "bad product"}, 400)
                grant_product(c, uid, prod, "mock", "")
                u = get_user(c, uid)
                myth, energy, rigs, rate = touch(u, c, now)
                u = get_user(c, uid)
                return self.send_json({"ok": True, "state": payload(u, rigs, rate), "mock": True})
            if p == "/api/admin/add":
                import os as _os
                if str(data.get("admin_key", "")) != _os.environ.get("ADMIN_KEY", "") or not _os.environ.get("ADMIN_KEY"):
                    return self.send_json({"ok": False, "error": "no"}, 403)
                auid = str(data.get("user_id", ""))[:64]
                try:
                    amt = float(data.get("myth", 0))
                except Exception:
                    amt = 0
                au = get_user(c, auid)
                if not au:
                    return self.send_json({"ok": False, "error": "nouser"}, 400)
                c.execute("UPDATE users SET myth=myth+? WHERE user_id=?", (amt, auid))
                c.commit()
                return self.send_json({"ok": True, "added": amt})
            if p == "/api/ton/save_wallet":
                addr = str(data.get("address", "") or "")[:64]
                c.execute("UPDATE users SET ton_wallet=? WHERE user_id=?", (addr, uid))
                try:
                    c.execute("INSERT INTO wallets(user_id,ton_address,updated) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET ton_address=EXCLUDED.ton_address, updated=EXCLUDED.updated", (uid, addr, now)) if c.pg else c.execute("INSERT OR REPLACE INTO wallets(user_id,ton_address,updated) VALUES(?,?,?)", (uid, addr, now))
                except Exception:
                    pass
                c.commit()
                return self.send_json({"ok": True, "address": addr})
            if p == "/api/ton/buy_premium":
                tx = str(data.get("tx", "") or "")[:128]
                addr = str(data.get("address", "") or u["ton_wallet"] or "")[:64]
                if not tx:
                    return self.send_json({"ok": False, "error": "need tx hash"}, 400)
                exists = _row(c.execute("SELECT COUNT(*) n FROM purchases WHERE tx=?", (tx,)).fetchone())["n"]
                if exists:
                    return self.send_json({"ok": False, "error": "tx used"}, 400)
                ok, info = verify_ton_payment(tx, uid, addr)
                if not ok:
                    return self.send_json({"ok": False, "error": info}, 400)
                if tx.startswith("mock_") and (u["premium"] or 0) >= 1:
                    return self.send_json({"ok": False, "error": "Έχεις ήδη το δωρεάν demo Premium. Για κι άλλο χρειάζεται αληθινή πληρωμή TON."}, 400)
                grant_product(c, uid, "ton_premium", "ton", tx)
                u = get_user(c, uid)
                myth, energy, rigs, rate = touch(u, c, now)
                u = get_user(c, uid)
                return self.send_json({"ok": True, "state": payload(u, rigs, rate), "verify": info})
            return self.send_json({"ok": False, "error": "unknown"}, 404)
        finally:
            c.close()

if __name__ == "__main__":
    db().close()
    srv = ThreadingHTTPServer((config.HOST, config.PORT), H)
    print(f"Olympos Mine running on http://{config.HOST}:{config.PORT}/")
    print(f"DB: {config.DB_PATH}")
    srv.serve_forever()
