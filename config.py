"""Olympos Mine - config with auto .env (stdlib only)."""
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# auto-load .env (KEY=VAL per line, no deps)
_ENV = os.path.join(BASE_DIR, ".env")
if os.path.isfile(_ENV):
    try:
        with open(_ENV, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except Exception:
        pass

DB_PATH = os.path.join(BASE_DIR, "data", "olympos.db")
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
WEBAPP_URL = os.environ.get("WEBAPP_URL", f"http://{HOST}:{PORT}/")

TAP_REWARD = 1
TAP_MAX_PER_REQUEST = 50
ENERGY_MAX = 1000
ENERGY_REGEN_PER_SEC = 1
ZEUS_MULTIPLIER = 5
RIGS = {
    "pickaxe":  {"cost": 100,   "per_sec": 1,   "name": "Αξίνα"},
    "dwarf":    {"cost": 500,   "per_sec": 6,   "name": "Νάνος"},
    "stoa":     {"cost": 2000,  "per_sec": 30,  "name": "Στοά"},
    "triaina":  {"cost": 10000, "per_sec": 180, "name": "Τρίαινα"},
}
OFFLINE_CAP_SEC = 8 * 3600
ORACLES = [
    {"q": "Έχω βροντή αλλά δεν είμαι καταιγίδα. Ποιος είμαι;", "a": "διας"},
    {"q": "Με κρατάς στο χέρι, με ρίχνεις στη θάλασσα. Τι είμαι;", "a": "τριαινα"},
    {"q": "Ποια πόλη έχει Παρθενώνα;", "a": "αθηνα"},
]
SEASON_DAYS = 7
POLIS_LIST = ["athens", "sparta", "crete"]
POLIS_NAMES = {"athens": "Αθήνα", "sparta": "Σπάρτη", "crete": "Κρήτη"}

STARS_PRODUCTS = {
    "energy_full": {"title": "⚡ Full Energy", "desc": "Γέμισε ενέργεια στο 1000", "stars": 10, "effect": "energy"},
    "shield_7d":   {"title": "🛡️ Ασπίδα 7 ημερών", "desc": "Προστασία από raids", "stars": 50, "effect": "shield"},
    "turbo_rig":   {"title": "🚀 Turbo Rig", "desc": "+50/sec για πάντα", "stars": 150, "effect": "turbo"},
}
TON_WALLET = os.environ.get("TON_WALLET", "")
TON_PREMIUM_PRICE = float(os.environ.get("TON_PREMIUM_PRICE", "0.5"))
TON_API_KEY = os.environ.get("TON_API_KEY", "")
PREMIUM_RIG_PER_SEC = 50

# --- Olympos extras: daily, quests, tournament, ads ---
DAILY_REWARDS = [0, 100, 200, 350, 500, 750, 1000, 1500]
QUESTS = [
    {"code": "tap100", "need": 100, "reward": 300},
    {"code": "rig3", "need": 3, "reward": 400},
    {"code": "oracle1", "need": 1, "reward": 200},
    {"code": "raid1", "need": 1, "reward": 200},
]
TOURNAMENT_PRIZES = [5000, 3000, 2000]
ADSGRAM_BLOCK_ID = os.environ.get("ADSGRAM_BLOCK_ID", "")
ADS_REWARD_ENERGY = 400
ADS_COOLDOWN_SEC = 60
ADS_MAX_PER_DAY = 20
