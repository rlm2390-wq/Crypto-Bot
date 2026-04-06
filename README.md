# RIZZ CRYPTO ENGINE v3.0

## File Structure
```
rizz-crypto-engine/
├── engine.py               ← entry point (Flask + engine loop)
├── config.py               ← all settings, credentials, asset rules
├── .env                    ← your local keys (NEVER commit this)
├── .env.example            ← template — copy to .env and fill in
├── .gitignore
├── requirements.txt
├── Procfile
│
├── exchanges/
│   ├── __init__.py         ← exchange registry
│   ├── base.py             ← shared interface
│   ├── coinbase.py         ← Coinbase connector
│   └── other_exchanges.py  ← Kraken, Binance, Uphold, Bitrue
│
├── wallets/
│   ├── __init__.py         ← wallet registry
│   ├── base.py             ← shared interface
│   ├── ledger.py           ← Ledger (read-only, THE VAULT)
│   ├── evm_wallet.py       ← MetaMask ETH/MATIC/ARB/OP + Bifrost SGB/FLR + XDC
│   └── other_wallets.py    ← Phantom (SOL), Keplr (ATOM)
│
├── layers/
│   ├── __init__.py
│   └── all_layers.py       ← Vault, Swing, Yield, Side Bets logic
│
├── core/
│   ├── __init__.py
│   ├── logger.py           ← activity log
│   ├── state.py            ← shared portfolio state
│   ├── approvals.py        ← approval queue + Telegram bridge
│   └── safety.py           ← safety gate checks
│
└── templates/
    └── dashboard.html      ← full control panel
```

---

## Phase 1 — Run Locally (Simulation)

```bash
# 1. Clone repo
git clone https://github.com/YOU/rizz-crypto-engine
cd rizz-crypto-engine

# 2. Create .env from template
cp .env.example .env
# Fill in DASHBOARD_SECRET at minimum

# 3. Install dependencies
pip install flask requests python-dotenv

# 4. Run
python engine.py

# 5. Open dashboard
# http://localhost:5000?secret=YOUR_DASHBOARD_SECRET
```

Everything runs in simulation — no real trades, no keys needed yet.

---

## Phase 2 — Run Locally (Live Trading)

1. Set `SIMULATION_MODE=false` in `.env`
2. Add your exchange API keys to `.env`
3. Add your wallet addresses and private keys to `.env`
4. Uncomment dependencies in `requirements.txt` and install:
   ```bash
   pip install ccxt web3 python-dotenv flask requests
   ```
5. Wire in Infura (or Alchemy) key for ETH RPC in `.env`:
   ```
   ETH_RPC_URL=https://mainnet.infura.io/v3/YOUR_KEY
   ```
6. Run and test with small amounts first

---

## Phase 3 — Deploy to Railway

1. Push all files to GitHub (**never commit `.env`**)
2. Railway → New Project → Deploy from GitHub → select repo
3. Go to **Variables** tab and add all values from your `.env`:

| Variable | Notes |
|---|---|
| `SIMULATION_MODE` | `false` for live |
| `DASHBOARD_SECRET` | strong password |
| `TELEGRAM_BOT_TOKEN` | from @BotFather |
| `TELEGRAM_CHAT_ID` | from @userinfobot |
| `COINBASE_API_KEY` | etc. |
| `COINBASE_API_SECRET` | |
| `COINBASE_PASSPHRASE` | |
| `KRAKEN_API_KEY` | |
| `KRAKEN_API_SECRET` | |
| `BINANCE_API_KEY` | |
| `BINANCE_API_SECRET` | |
| `UPHOLD_API_KEY` | |
| `UPHOLD_API_SECRET` | |
| `BITRUE_API_KEY` | |
| `BITRUE_API_SECRET` | |
| `PHANTOM_SOL_ADDRESS` | |
| `PHANTOM_SOL_PRIVATE_KEY` | |
| `METAMASK_ETH_ADDRESS` | |
| `METAMASK_ETH_PRIVATE_KEY` | |
| `BIFROST_SGB_ADDRESS` | |
| `BIFROST_SGB_PRIVATE_KEY` | |
| `BIFROST_FLR_ADDRESS` | |
| `BIFROST_FLR_PRIVATE_KEY` | |
| `KEPLR_ATOM_ADDRESS` | |
| `KEPLR_ATOM_PRIVATE_KEY` | |
| `XDC_ADDRESS` | |
| `XDC_PRIVATE_KEY` | |
| `LEDGER_ETH_ADDRESS` | public only |
| `LEDGER_BTC_ADDRESS` | public only |
| `ETH_RPC_URL` | Infura/Alchemy endpoint |

4. Deploy. Railway gives you a public URL.
5. Bookmark: `https://YOUR-URL.railway.app?secret=YOUR_SECRET`

---

## Telegram Setup

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy token
2. Message [@userinfobot](https://t.me/userinfobot) → copy your chat ID
3. Start your bot once (`/start`)

**Commands:**
- `/approve <id>` — approve a pending action
- `/deny <id>`    — deny a pending action
- `/status`       — get portfolio summary
- `/pause`        — pause the engine
- `/resume`       — resume the engine

---

## Reward Routing

Edit `REWARD_ROUTING` in `config.py` to control where each asset's rewards go:

```python
REWARD_ROUTING = {
    "SGB":  "exchange",  # Bifrost SGB rewards → Coinbase
    "FLR":  "exchange",  # Bifrost FLR rewards → Coinbase
    "ATOM": "ledger",    # Keplr ATOM rewards → Ledger
    "ETH":  "ledger",    # ETH staking → Ledger
    ...
}
```

---

## Going Live Checklist

- [ ] Tested simulation mode locally — no errors
- [ ] All exchange API keys added and tested
- [ ] All wallet addresses pasted in
- [ ] Telegram bot set up and responding
- [ ] Dashboard accessible at Railway URL
- [ ] Approval flow tested (trigger one + approve from phone)
- [ ] `SIMULATION_MODE=false` set in Railway variables
- [ ] Started with small swing stack amounts to verify trades execute
