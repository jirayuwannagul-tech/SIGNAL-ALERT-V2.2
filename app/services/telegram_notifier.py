import logging
import requests
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from typing import Dict, Optional

logger = logging.getLogger(__name__)

# =========================
# Helper
# =========================

def _to_int(v):
    try:
        return int(v) if v is not None and str(v).strip() != "" else None
    except:
        return None


# =========================
# Telegram Notifier
# =========================

class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{self.token}"

        # Topic IDs (Forum Threads)
        self.topics = {
            "normal": _to_int(os.getenv("TOPIC_NORMAL_ID")),
            "vip": _to_int(os.getenv("TOPIC_VIP_ID")),
            "chat": _to_int(os.getenv("TOPIC_CHAT_ID")),
            "member": _to_int(os.getenv("TOPIC_MEMBER_ID")),
        }

        logger.info("TelegramNotifier ready")

    # =========================
    # ✅ ADDED: Resolve Topic By Timeframe
    # (เพิ่มฟังก์ชันใหม่ ไม่แตะโค้ดเดิม)
    # =========================
    def resolve_topic_id(self, timeframe: str, fallback: Optional[int] = None) -> Optional[int]:
        tf = (timeframe or "").lower().strip()

        if tf in ("1d", "1day", "d"):
            return self.topics.get("vip") or fallback


        return fallback

    # =========================
    # Core Send
    # =========================

    def send_message(self, text: str, thread_id: Optional[int] = None):
        try:
            url = f"{self.api_url}/sendMessage"

            safe = text.replace("```", "'''")
            wrapped = f"```\n{safe}\n```"

            payload = {
                "chat_id": self.chat_id,
                "text": wrapped,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            }

            if thread_id:
                payload["message_thread_id"] = thread_id

            res = requests.post(url, json=payload, timeout=10)
            return res.json()

        except Exception as e:
            logger.error(f"Telegram Send Error: {e}")


    # =========================
    # Signal Alert (VIP)
    # =========================

    def send_signal_alert(self, analysis: Dict, topic_id: Optional[int] = None):
        try:
            symbol = analysis.get("symbol", "UNKNOWN")
            timeframe = (analysis.get("timeframe") or "1d").lower()
            price = float(analysis.get("current_price", 0) or 0)

            signals = analysis.get("signals", {}) or {}
            risk = analysis.get("risk_levels", {}) or {}
            strength = analysis.get("signal_strength", 0)

            entry = float(risk.get("entry_price", price) or 0)
            sl = float(risk.get("stop_loss", 0) or 0)
            tp1 = float(risk.get("take_profit_1", 0) or 0)
            tp2 = float(risk.get("take_profit_2", 0) or 0)
            tp3 = float(risk.get("take_profit_3", 0) or 0)

            # เวลาไทย
            now_th = datetime.now(ZoneInfo("Asia/Bangkok")).strftime("%H:%M:%S")

            # Direction (support signals + explicit direction)
            direction = (analysis.get("direction", "") or "").upper()
            is_long = bool(signals.get("buy")) or direction == "LONG"
            is_short = bool(signals.get("short")) or direction == "SHORT"

            if is_long and not is_short:
                side = "LONG"
                emoji = "🟢"
                sl_pct = ((sl - entry) / entry) * 100 if entry else 0
                tp1_pct = ((tp1 - entry) / entry) * 100 if entry else 0
                tp2_pct = ((tp2 - entry) / entry) * 100 if entry else 0
                tp3_pct = ((tp3 - entry) / entry) * 100 if entry else 0
            else:
                side = "SHORT"
                emoji = "🔴"
                sl_pct = ((sl - entry) / entry) * 100 if entry else 0
                tp1_pct = -((entry - tp1) / entry) * 100 if entry else 0
                tp2_pct = -((entry - tp2) / entry) * 100 if entry else 0
                tp3_pct = -((entry - tp3) / entry) * 100 if entry else 0

            # RR (ใช้ abs ให้เป็นบวกเสมอ)
            if sl_pct != 0:
                rr1 = abs(tp1_pct / sl_pct)
                rr2 = abs(tp2_pct / sl_pct)
                rr3 = abs(tp3_pct / sl_pct)
            else:
                rr1 = rr2 = rr3 = 0.0

            # Header + Strategy (1D only)
            header = f"{emoji}⚡ CDC ALERT ⚡{emoji}"
            strategy = "1D SWING"

            # =========================
            # ✅ ADDED: Auto route by timeframe when topic_id not provided
            # (เพิ่มโค้ดใหม่ ไม่ลบ/ไม่แก้โค้ดเดิม)
            # =========================
            target_thread = topic_id or self.topics["vip"]
            if topic_id is None:
                resolved = self.resolve_topic_id(timeframe, fallback=target_thread)
                target_thread = resolved

            # ✅ ใส่ logic สร้างข้อความแบบ LONG/SHORT ในก้อนนี้เลย
            is_long = str(side).upper() == "LONG"
            emoji = "🐂" if is_long else "🐻"

            if is_long:
                header = "🟢🚀 ปู๊น ปู๊น! รถไฟขาขึ้นมาแล้วจ้า~"
                entry_label = "💰 ขึ้นรถตรงนี้เลย"
                sl_label = "🛑 ถ้าร่วงมาถึงนี่... บ๊ายบาย"
                tp1_suffix, tp2_suffix, tp3_suffix = "กินก่อน~", "อร่อยอีก~", "ฟินสุดๆ~"
                footer_tip = "💡 ได้กำไรอย่าลืมกันข้าวบอทด้วยนะ 555~"
            else:
                header = "🔴📉 ระวัง! หมีออกล่าแล้วจ้า~"
                entry_label = "💰 กระโดดลงตรงนี้"
                sl_label = "🛑 ถ้าดีดขึ้นมานี่... หนีเลย"
                tp1_suffix, tp2_suffix, tp3_suffix = "จิ้มก่อน~", "ลึกอีก~", "ถึงก้นเหว~"
                footer_tip = "💡 ขาดทุนอย่าโทษบอทนะ ฮิ้วววว~"

            message = (
                f"{header}\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"📊 Strategy: {strategy}\n"
                f"🪙 {symbol} ({timeframe}) - {side} {emoji}\n"
                f"{entry_label}: {entry:,.4f}\n"
                f"{sl_label}: {sl:,.4f} ({sl_pct:+.1f}%)\n"
                f"🎯 เป้า 1: {tp1:,.4f} ({tp1_pct:+.1f}%) {rr1:.1f}:1 {tp1_suffix}\n"
                f"🎯 เป้า 2: {tp2:,.4f} ({tp2_pct:+.1f}%) {rr2:.1f}:1 {tp2_suffix}\n"
                f"🎯 เป้า 3: {tp3:,.4f} ({tp3_pct:+.1f}%) {rr3:.1f}:1 {tp3_suffix}\n"
                f"💪 Strength: {strength}%\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"🕐 {now_th}\n"
                f"🤖 บอทจำเฉย v2.2\n"
                f"{footer_tip}"
            )

            self.send_message(message, thread_id=target_thread)
            logger.info(f"Telegram signal sent: {symbol}")

    # =========================
    # Membership Room
    # =========================

    def send_membership_alert(self, text: str):
        self.send_message(text, thread_id=self.topics["member"])

    # =========================
    # DM User
    # =========================

    def send_direct_message(self, user_id: str, text: str):
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {
                "chat_id": user_id,
                "text": text,
                "parse_mode": "Markdown"
            }
            requests.post(url, json=payload, timeout=10)
        except:
            pass
