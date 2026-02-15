import os
from datetime import datetime
from typing import Dict
from app.services.telegram_notifier import TelegramNotifier
from app.services.position_manager import PositionManager
from app.services.data_manager import DataManager
from app.utils.pnl_utils import calculate_pnl_pct
# =========================================================
# DAILY SUMMARY SERVICE (SEND TO NORMAL TOPIC ONLY)
# =========================================================
def _to_int_env(key: str, default: int = 0) -> int:
    v = os.getenv(key)
    try:
        return int(v) if v is not None else default
    except Exception:
        return default
def send_daily_summary():
    tg = TelegramNotifier(token=os.getenv("TELEGRAM_BOT_TOKEN"), chat_id=os.getenv("TELEGRAM_CHAT_ID"))
    data_manager = DataManager()
    pm = PositionManager(data_manager)
    positions = pm.get_active_positions()
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

    # ===============================
    # สถิติวันนี้ (Open / Close / TP / SL)
    # ===============================
    tz_today = datetime.now().date()
    opened_today = 0
    closed_today = 0
    tp_today = 0
    sl_today = 0

    # โหลดทุก position (รวมที่ปิดแล้ว ถ้ามีใน store)
    all_positions = getattr(pm, "active_positions", {}) or {}
    if isinstance(all_positions, dict):
        all_positions = list(all_positions.values())

    for p in all_positions:
        try:
            # นับเปิดวันนี้
            entry_time = p.get("entry_time")
            if entry_time:
                dt = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
                if dt.date() == tz_today:
                    opened_today += 1

            # นับปิดวันนี้
            close_time = p.get("close_time")
            if close_time:
                dt = datetime.fromisoformat(close_time.replace("Z", "+00:00"))
                if dt.date() == tz_today:
                    closed_today += 1

            # นับ TP / SL วันนี้จาก events
            events = p.get("events") or {}
            for k in ("TP1", "TP2", "TP3", "SL"):
                e = events.get(k)
                if not e or not isinstance(e, dict):
                    continue
                ts = e.get("timestamp")
                if not ts:
                    continue
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if dt.date() != tz_today:
                    continue
                if k == "SL":
                    sl_today += 1
                else:
                    tp_today += 1
        except Exception:
            continue
    tf_1d = 0
    tf_15m = 0
    for p in positions or []:
        tf = (p.get("timeframe") or "").lower()
        if tf == "1d":
            tf_1d += 1
        elif tf == "15m":
            tf_15m += 1
    header = [
        "📊 *สรุปผลการเทรดประจำวัน*",
        f"📅 วันที่ `{datetime.now().strftime('%d/%m/%Y')}`",
        f"📦 จำนวนไม้ที่เปิดอยู่ตอนนี้: {len(positions) if positions else 0}",
        f"🆕 เปิดวันนี้: {opened_today} ไม้",
        f"🔒 ปิดวันนี้: {closed_today} ไม้",
        f"🎯 TP วันนี้: {tp_today} ครั้ง",
        f"🛑 SL วันนี้: {sl_today} ครั้ง",
        f"   • TF 1D: {tf_1d} ไม้",
        f"   • TF 15m: {tf_15m} ไม้",
        "━━━━━━━━━━━━━━━━━━",
    ]
    topic_normal = _to_int_env("TOPIC_NORMAL_ID", 0)
    if not positions:
        tg.send_message("\n".join(header + ["❌ ไม่มี Position วันนี้"]), thread_id=topic_normal)
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
        pnl = calculate_pnl_pct(direction, entry, current)
        hit = []
        if direction == "LONG":
            if current <= sl:
                hit.append("SL ❌")
            if current >= tp1:
                hit.append("TP1 ✅")
            if current >= tp2:
                hit.append("TP2 ✅")
            if current >= tp3:
                hit.append("TP3 ✅")
        else:
            if current >= sl:
                hit.append("SL ❌")
            if current <= tp1:
                hit.append("TP1 ✅")
            if current <= tp2:
                hit.append("TP2 ✅")
            if current <= tp3:
                hit.append("TP3 ✅")
        if not hit:
            hit.append("⏳ ยังไม่ถึงเป้า")
        emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
        block = (
            f"🪙 *{symbol}*  |  TF `{tf}`  |  {direction}\n"
            f"💰 ราคาเข้า: `{entry:,.2f}`\n"
            f"📍 ราคาปัจจุบัน: `{current:,.2f}`\n"
            f"🛑 Stop Loss: `{sl:,.2f}`\n"
            f"🎯 เป้ากำไร TP1: `{tp1:,.2f}`\n"
            f"🎯 เป้ากำไร TP2: `{tp2:,.2f}`\n"
            f"🎯 เป้ากำไร TP3: `{tp3:,.2f}`\n"
            f"{emoji} กำไร/ขาดทุน: `{pnl:+.2f}%`\n"
            f"📌 สถานะปัจจุบัน: {' | '.join(hit)}\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        blocks.append(block)
    tg.send_message("\n".join(header + blocks), thread_id=topic_normal)
