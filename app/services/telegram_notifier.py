import logging
import requests
import os
from datetime import datetime
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
    # Core Send
    # =========================

    def send_message(self, text: str, thread_id: Optional[int] = None):
        try:
            url = f"{self.api_url}/sendMessage"

            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
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
            timeframe = analysis.get("timeframe", "4h")
            price = analysis.get("current_price", 0)

            signals = analysis.get("signals", {})
            risk = analysis.get("risk_levels", {})
            strength = analysis.get("signal_strength", 0)

            entry = risk.get("entry_price", price)
            sl = risk.get("stop_loss", 0)
            tp1 = risk.get("take_profit_1", 0)
            tp2 = risk.get("take_profit_2", 0)
            tp3 = risk.get("take_profit_3", 0)

            target_thread = topic_id or self.topics["vip"]

            # ---- TF (support list) ----
            tfs = analysis.get("timeframes") or analysis.get("tf_list") or analysis.get("tf") or analysis.get("timeframe") or "1D / 4H / 15m"
            if isinstance(tfs, list):
                tf_text = " / ".join(tfs)
            else:
                tf_text = str(tfs).strip() if str(tfs).strip() else "1D / 4H / 15m"
            # ---------------------------


            # Direction (support signals + explicit direction)
            direction = analysis.get("direction", "").upper()
            is_long = bool(signals.get("buy")) or direction == "LONG"
            is_short = bool(signals.get("short")) or direction == "SHORT"

            if is_long and not is_short:
                side = "LONG"
                emoji = "🟢"
                header = "🟢⚡ SIGNAL ALERT ⚡🟢"
                sl_pct = ((sl - entry) / entry) * 100 if entry else 0
                tp1_pct = ((tp1 - entry) / entry) * 100 if entry else 0
                tp2_pct = ((tp2 - entry) / entry) * 100 if entry else 0
                tp3_pct = ((tp3 - entry) / entry) * 100 if entry else 0
            else:
                side = "SHORT"
                emoji = "🔴"
                header = "🔴⚡ SIGNAL ALERT ⚡🔴"
                sl_pct = ((sl - entry) / entry) * 100 if entry else 0
                tp1_pct = -((entry - tp1) / entry) * 100 if entry else 0
                tp2_pct = -((entry - tp2) / entry) * 100 if entry else 0
                tp3_pct = -((entry - tp3) / entry) * 100 if entry else 0


            message = (
                f"{header}\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"🪙 *{symbol}* {side} {emoji}\n"
                f"⏱ TF: `{tf_text}`\n"
                f"💵 Entry: `{entry:,.6f}`\n"
                f"🛑 SL: `{sl:,.6f}` ({sl_pct:+.1f}%)\n"
                f"🎯 TP1: `{tp1:,.6f}` ({tp1_pct:+.1f}%)\n"
                f"🎯 TP2: `{tp2:,.6f}` ({tp2_pct:+.1f}%)\n"
                f"🎯 TP3: `{tp3:,.6f}` ({tp3_pct:+.1f}%)\n"
                f"💪 Strength: `{strength}%`\n"
                f"🕐 `{datetime.now().strftime('%H:%M:%S')}`"
            )

            self.send_message(message, thread_id=target_thread)
            logger.info(f"Telegram signal sent: {symbol}")

        except Exception as e:
            logger.error(f"Telegram Alert Error: {e}")

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
