import os
from datetime import datetime
from typing import Dict

from app.services.telegram_notifier import TelegramNotifier
from app.services.position_manager import PositionManager
from app.services.data_manager import DataManager

# =========================================================
# DAILY SUMMARY SERVICE (SEND TO NORMAL TOPIC ONLY)
# =========================================================

def _calc_pnl_pct(direction: str, entry: float, current: float) -> float:
    if entry == 0:
        return 0.0
    if direction == "LONG":
        return ((current - entry) / entry) * 100
    return ((entry - current) / entry) * 100


def _to_int_env(key: str, default: int = 0) -> int:
    v = os.getenv(key)
    try:
        return int(v) if v is not None else default
    except Exception:
        return default


def send_daily_summary():
    tg = TelegramNotifier(
        token=os.getenv("TELEGRAM_BOT_TOKEN"),
        chat_id=os.getenv("TELEGRAM_CHAT_ID")
    )

    data_manager = DataManager()
    pm = PositionManager(data_manager)

    positions = pm.get_active_positions()

    # ✅ normalize: ให้เป็น list[dict] เสมอ
    if isinstance(positions, dict):
        positions = list(positions.values())
    elif isinstance(positions, list):
        if positions and isinstance(positions[0], str):
            resolved = []
            store = getattr(pm, "active_positions", {}) or {}
            for pid in positions:
                v = store.get(pid)
                if isinstance(v, dict):
                    resolved.append(v)
            positions = resolved
    else:
        positions = []

    # ✅ นับแยก timeframe จาก active positions
    tf_1d = 0
    tf_15m = 0
    for p in positions or []:
        tf = (p.get("timeframe") or "").lower()
        if tf == "1d":
            tf_1d += 1
        elif tf == "15m":
            tf_15m += 1

    header = [
        "📊 *DAILY SUMMARY*",
        f"📅 `{datetime.now().strftime('%Y-%m-%d')}`",
        f"📦 Total Signals: {len(positions) if positions else 0}",
        f"   • 1D: {tf_1d}",
        f"   • 15m: {tf_15m}",
        f"🟢 Active Positions: {len(positions) if positions else 0}",
        "🔴 Closed Positions: 0",
        "━━━━━━━━━━━━━━━━━",
    ]

    topic_normal = _to_int_env("TOPIC_NORMAL_ID", 0)

    if not positions:
        tg.send_message(
            "\n".join(header + ["❌ ไม่มี Position วันนี้"]),
            thread_id=topic_normal
        )
        return

    blocks = []

    for p in positions:
        symbol = p.get("symbol")
        tf = p.get("timeframe")
        direction = p.get("direction")
        entry = p.get("entry_price", 0)
        current = p.get("current_price", entry)

        sl = p.get("stop_loss", 0)
        tp1 = p.get("take_profit_1", 0)
        tp2 = p.get("take_profit_2", 0)
        tp3 = p.get("take_profit_3", 0)

        pnl = _calc_pnl_pct(direction, entry, current)

        hit = []
        if direction == "LONG":
            if current <= sl: hit.append("SL ❌")
            if current >= tp1: hit.append("TP1 ✅")
            if current >= tp2: hit.append("TP2 ✅")
            if current >= tp3: hit.append("TP3 ✅")
        else:
            if current >= sl: hit.append("SL ❌")
            if current <= tp1: hit.append("TP1 ✅")
            if current <= tp2: hit.append("TP2 ✅")
            if current <= tp3: hit.append("TP3 ✅")

        if not hit:
            hit.append("⏳ ยังไม่ถึงเป้า")

        emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"

        block = (
            f"🪙 *{symbol}* `{tf}` {direction}\n"
            f"💵 Entry: `{entry:,.2f}`\n"
            f"🛑 SL: `{sl:,.2f}`\n"
            f"🎯 TP1: `{tp1:,.2f}`\n"
            f"🎯 TP2: `{tp2:,.2f}`\n"
            f"🎯 TP3: `{tp3:,.2f}`\n"
            f"{emoji} *PnL:* `{pnl:+.2f}%`\n"
            f"📌 Status: {' | '.join(hit)}\n"
            f"━━━━━━━━━━━━━━━━━"
        )
        blocks.append(block)

    # ✅ ส่งครั้งเดียวไปห้องคุยทั่วไป
    tg.send_message("\n".join(header + blocks), thread_id=topic_normal)