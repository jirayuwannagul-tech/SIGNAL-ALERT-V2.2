import os
from datetime import datetime
from typing import Dict

from app.services.telegram_notifier import TelegramNotifier
from app.services.position_manager import PositionManager
from app.services.data_manager import DataManager

# =========================================================
# DAILY SUMMARY SERVICE (FIXED for REAL PositionManager)
# =========================================================

def _calc_pnl_pct(direction: str, entry: float, current: float) -> float:
    if entry == 0:
        return 0.0
    if direction == "LONG":
        return ((current - entry) / entry) * 100
    return ((entry - current) / entry) * 100


def send_daily_summary():
    tg = TelegramNotifier(
        token=os.getenv("TELEGRAM_BOT_TOKEN"),
        chat_id=os.getenv("TELEGRAM_CHAT_ID")
    )

    # ✅ ใช้ DataManager ตัวจริง
    data_manager = DataManager()
    pm = PositionManager(data_manager)

    positions = pm.get_active_positions()

    header = [
        "📊 *DAILY SUMMARY*",
        f"📅 `{datetime.now().strftime('%Y-%m-%d')}`",
        "━━━━━━━━━━━━━━━━━"
    ]

    if not positions:
        tg.send_message(
            "\n".join(header + ["❌ ไม่มี Position วันนี้"]),
            thread_id=os.getenv("TOPIC_CHAT_ID")
        )
        return

    vip_blocks = []
    free_blocks = []

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
            f"�� TP1: `{tp1:,.2f}`\n"
            f"🎯 TP2: `{tp2:,.2f}`\n"
            f"🎯 TP3: `{tp3:,.2f}`\n"
            f"{emoji} *PnL:* `{pnl:+.2f}%`\n"
            f"📌 Status: {' | '.join(hit)}\n"
            f"━━━━━━━━━━━━━━━━━"
        )

        if p.get("is_vip", True):
            vip_blocks.append(block)
        else:
            free_blocks.append(block)

    if vip_blocks:
        tg.send_message(
            "\n".join(header + vip_blocks),
            thread_id=os.getenv("TOPIC_VIP_ID")
        )

    if free_blocks:
        tg.send_message(
            "\n".join(header + free_blocks),
            thread_id=os.getenv("TOPIC_NORMAL_ID")
        )
