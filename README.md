# RIZZ CRYPTO ENGINE — Deploy Guide

## Files
```
engine.py              ← main engine + Flask dashboard
templates/
  dashboard.html       ← control panel UI
requirements.txt
Procfile               ← Railway entry point
```

---

## 1. GitHub

Push all files to a new repo (e.g. `rizz-crypto-engine`).

---

## 2. Railway Setup

1. New Project → Deploy from GitHub → select your repo
2. Railway auto-detects the `Procfile` and runs `python engine.py`
3. Go to **Variables** tab and add:

| Variable | Value |
|---|---|
| `SIMULATION_MODE` | `true` (change to `false` when going live) |
| `DASHBOARD_SECRET` | any strong password |
| `TELEGRAM_BOT_TOKEN` | from BotFather (see below) |
| `TELEGRAM_CHAT_ID` | your Telegram user ID |
| `API_KEY` | exchange API key |
| `API_SECRET` | exchange API secret |
| `LOOP_INTERVAL` | `60` (seconds between loops) |
| `LARGE_MOVE_USD` | `100` |
| `PORT` | `5000` |

4. Deploy. Railway gives you a public URL like `https://rizz-engine.up.railway.app`

---

## 3. Dashboard Access

Open: `https://your-railway-url.app/?secret=YOUR_DASHBOARD_SECRET`

Bookmark that URL. Open it on your phone or laptop to see live status and handle approvals.

---

## 4. Telegram Bot Setup

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` — follow prompts — copy the **bot token**
3. Get your chat ID: message [@userinfobot](https://t.me/userinfobot)
4. Add both to Railway variables above
5. Start your bot by messaging it once (`/start`)

When the engine needs approval, it will message you with:
```
/approve abc12345
/deny abc12345
```
Reply with one of those commands to resolve it.

---

## 5. Going Live (when ready)

1. Set `SIMULATION_MODE=false` in Railway variables
2. Uncomment `ccxt` in `requirements.txt`
3. Wire in the 3 `# TODO` stubs in `engine.py`:
   - `get_price()` — use `ccxt` exchange ticker
   - `get_balance()` — use `ccxt` fetch_balance
   - `execute_trade()` — use `ccxt` create_order
4. Redeploy

---

## Safety Rules (built-in)

- Engine auto-pauses on high gas, volatility, exchange errors
- Vault assets can never decrease automatically — always requires approval
- All moves above `LARGE_MOVE_USD` require approval
- Approvals time out after `APPROVAL_TIMEOUT` seconds (default 5 min) and are denied
