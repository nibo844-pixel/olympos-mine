# 🏛️ Olympos Mine — έτοιμο, δεν βάζεις τίποτα

## Παίξε τώρα (0 ρυθμίσεις)
```bash
./setup.sh
./run.sh
```
Άνοιξε `http://127.0.0.1:8000/` — παίζει αμέσως σε demo mode.

## Αν θες αληθινά λεφτά (όταν είσαι έτοιμος)
1. BotFather -> `/newbot` -> πάρε token -> βάλτο στο `.env` σαν `BOT_TOKEN=...`
2. Βάλε στο `.env` `WEBAPP_URL=https://<domain>/` και `TON_WALLET=UQ...` (το πορτοφόλι σου)
3. Τρέξε `python3 tools/setup_bot.py` (βάζει κουμπιά + commands μόνο του)
4. Τρέξε `python3 bot.py`

Τέλος. Stars δουλεύουν μόνα τους (XTR invoices), TON ελέγχεται μόνο του μέσω toncenter.
