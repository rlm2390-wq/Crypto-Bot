"""core/approvals.py — Approval queue, Telegram notifications, resolution."""

import threading
import uuid
import time
from datetime import datetime

import requests as http_requests

from core.logger import activity
from core.state  import APPROVAL_QUEUE, approval_events, approval_results


def request_approval(description: str, usd_value: float = 0.0) -> bool:
    """
    Queue an approval request. Notifies via Telegram + dashboard.
    Blocks the calling thread until approved, denied, or timed out.
    Returns True if approved.
    """
    from config import APPROVAL_TIMEOUT
    approval_id = str(uuid.uuid4())
    event = threading.Event()
    approval_events[approval_id] = event

    entry = {
        "id":          approval_id,
        "description": description,
        "usd_value":   usd_value,
        "created_at":  datetime.now().isoformat(),
        "status":      "pending",
        "resolved_at": None,
    }
    APPROVAL_QUEUE.append(entry)
    activity(f"[APPROVAL PENDING] {description} | ${usd_value:,.2f}", "WARNING")

    _telegram_send_approval(approval_id, description, usd_value)

    resolved = event.wait(timeout=APPROVAL_TIMEOUT)
    if not resolved:
        entry["status"]      = "timeout"
        entry["resolved_at"] = datetime.now().isoformat()
        activity(f"[APPROVAL TIMEOUT] {description}", "WARNING")
        return False

    return approval_results.get(approval_id, False)


def resolve_approval(approval_id: str, result: bool):
    """Resolve a pending approval by ID. Called from dashboard API or Telegram."""
    for appr in APPROVAL_QUEUE:
        if appr["id"] == approval_id and appr["status"] == "pending":
            appr["status"]      = "approved" if result else "denied"
            appr["resolved_at"] = datetime.now().isoformat()
            approval_results[approval_id] = result
            ev = approval_events.get(approval_id)
            if ev:
                ev.set()
            activity(
                f"Approval {'APPROVED' if result else 'DENIED'}: {appr['description'][:60]}",
                "INFO" if result else "WARNING"
            )
            break


def _telegram_send_approval(approval_id: str, description: str, usd_value: float):
    from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    import os
    dashboard_url = os.environ.get("RAILWAY_STATIC_URL", "http://localhost:5000")
    msg = (
        f"⚠️ <b>APPROVAL REQUIRED</b>\n\n"
        f"{description}\n"
        f"Value: <b>${usd_value:,.2f}</b>\n\n"
        f"Dashboard: {dashboard_url}\n\n"
        f"Reply:\n"
        f"<code>/approve {approval_id[:8]}</code>\n"
        f"<code>/deny {approval_id[:8]}</code>"
    )
    telegram_send(msg)


def telegram_send(text: str):
    """Send a plain message via Telegram bot."""
    from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        http_requests.post(url, json={
            "chat_id":    TELEGRAM_CHAT_ID,
            "text":       text,
            "parse_mode": "HTML",
        }, timeout=10)
    except Exception as e:
        activity(f"Telegram send failed: {e}", "WARNING")


def poll_telegram_commands():
    """
    Background thread. Polls Telegram for /approve and /deny commands.
    Maps short ID prefix back to full approval ID and resolves it.
    """
    from config import TELEGRAM_BOT_TOKEN
    if not TELEGRAM_BOT_TOKEN:
        return
    last_update_id = 0
    while True:
        try:
            url  = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            resp = http_requests.get(
                url,
                params={"offset": last_update_id + 1, "timeout": 30},
                timeout=35
            )
            data = resp.json()
            for update in data.get("result", []):
                last_update_id = update["update_id"]
                msg  = update.get("message", {})
                text = msg.get("text", "").strip()
                if text.startswith("/approve ") or text.startswith("/deny "):
                    parts   = text.split()
                    cmd     = parts[0]
                    id_hint = parts[1] if len(parts) > 1 else ""
                    for appr in APPROVAL_QUEUE:
                        if appr["id"].startswith(id_hint) and appr["status"] == "pending":
                            result = (cmd == "/approve")
                            resolve_approval(appr["id"], result)
                            reply = "✅ Approved" if result else "❌ Denied"
                            telegram_send(f"{reply}: {appr['description'][:80]}")
                            break
                elif text == "/status":
                    _send_status_summary()
                elif text == "/pause":
                    from core.state import ENGINE_STATE
                    ENGINE_STATE["paused"]       = True
                    ENGINE_STATE["pause_reason"] = "Paused via Telegram"
                    activity("[ENGINE PAUSED] via Telegram", "WARNING")
                    telegram_send("⏸ Engine paused.")
                elif text == "/resume":
                    from core.state import ENGINE_STATE
                    ENGINE_STATE["paused"]       = False
                    ENGINE_STATE["pause_reason"] = ""
                    activity("[ENGINE RESUMED] via Telegram")
                    telegram_send("▶️ Engine resumed.")
        except Exception as e:
            activity(f"Telegram poll error: {e}", "WARNING")
        time.sleep(2)


def _send_status_summary():
    """Send a compact portfolio summary to Telegram."""
    from core.state import PORTFOLIO, ENGINE_STATE
    from config     import VAULT_ASSETS, YIELD_ASSETS, ACTIVE_SIDE_BETS
    try:
        lines = ["📊 <b>Engine Status</b>\n"]
        lines.append(f"Mode: {'SIMULATION' if ENGINE_STATE['simulation'] else 'LIVE'}")
        lines.append(f"Paused: {ENGINE_STATE['paused']}")
        lines.append(f"Loop: #{ENGINE_STATE['loop_count']}\n")
        lines.append("<b>Vault (exchange):</b>")
        for s in VAULT_ASSETS:
            e = PORTFOLIO.get(s, {})
            lines.append(f"  {s}: {e.get('balance',0):.4f} (locked: {e.get('vault_locked',0):.4f})")
        lines.append("\n<b>Active Side Bets:</b>")
        from core.state import ACTIVE_SIDE_BETS as asb
        for s in asb:
            e = PORTFOLIO.get(s, {})
            lines.append(f"  {s}: {e.get('balance',0):.2f}")
        telegram_send("\n".join(lines))
    except Exception as e:
        telegram_send(f"Status error: {e}")
