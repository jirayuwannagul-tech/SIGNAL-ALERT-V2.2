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
            "normal": int(os.getenv("TOPIC_NORMAL_ID", "2")),   # คุยทั่วไป
            "vip": int(os.getenv("TOPIC_VIP_ID", "18")),          # 1D signals
            "chat": int(os.getenv("TOPIC_CHAT_ID", "1")),         # TP/SL ทุก TF
            "15m": int(os.getenv("TOPIC_15M_ID", "249")),         # 15m signals
            "member": int(os.getenv("TOPIC_MEMBER_ID", "4")),     # อธิบาย
        }

        logger.info(f"TelegramNotifier ready | topics={self.topics}")

    # =========================
    # ✅ ADDED: Resolve Topic By Timeframe
    # (เพิ่มฟังก์ชันใหม่ ไม่แตะโค้ดเดิม)
    # =========================
    def resolve_topic_id(self, timeframe: str, fallback: Optional[int] = None) -> Optional[int]:
        tf = (timeframe or "").lower().strip()

        if tf in ("1d", "1day", "d"):
            return self.topics.get("vip") or fallback

        if tf in ("15m", "15min", "m15"):
            return self.topics.get("15m") or fallback

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
            # System Name by Timeframe
            # =========================
            tf = (timeframe or "").lower().strip()
            if tf in ("1d", "1day", "d"):
                system_name = "CDC ACTIONZONE+PULLBAC"
            elif tf in ("15m", "15min", "m15"):
                system_name = "EBRAV-15"
            else:
                system_name = "SYSTEM"

            # =========================================================
            # ROUTING RULES (5 ห้อง) - ใช้กับ send_signal_alert เท่านั้น
            #
            # Priority:
            # 1) ถ้าส่ง topic_id มา => ใช้ topic_id นั้นเสมอ (override)
            # 2) ถ้าไม่ส่ง topic_id:
            #    2.1) ถ้ามี analysis["route"] => route map ตามนี้
            #         - "signal_1d"  -> VIP (TOPIC_VIP_ID)
            #         - "signal_15m" -> 15M (TOPIC_15M_ID)
            #         - "tp_sl"      -> CHAT (TOPIC_CHAT_ID)
            #         - "normal"/"cross" -> NORMAL (TOPIC_NORMAL_ID)
            #         - "member"     -> MEMBER (TOPIC_MEMBER_ID)
            #    2.2) ถ้าไม่มี route => ใช้ timeframe:
            #         - 1d  -> VIP
            #         - 15m -> 15M
            #         - อื่นๆ -> NORMAL
            #
            # Debug:
            # ตั้ง ENV DEBUG_TELEGRAM_ROUTE=1 เพื่อดู log routing
            # =========================================================
            route = (analysis.get("route") or "").lower().strip()

            # override เสมอ ถ้า caller ส่งมา
            if topic_id is not None:
                target_thread = topic_id
                route_reason = f"override topic_id={topic_id}"
            else:
                # default fallback = ห้องทั่วไป
                fallback_thread = self.topics.get("normal")

                if route in ("tp_sl", "tpsl", "sl_tp", "sl/tp"):
                    target_thread = self.topics.get("chat") or fallback_thread
                    route_reason = f"route='{route}' -> chat"

                elif route in ("signal_1d", "entry_1d", "vip"):
                    target_thread = self.topics.get("vip") or fallback_thread
                    route_reason = f"route='{route}' -> vip"

                elif tf in ("15m", "15min", "m15"):
                    target_thread = self.topics.get("15m") or self.topics.get("chat") or fallback_thread
                    route_reason = f"timeframe='{tf}' -> 15m"

                elif route in ("cross", "normal"):
                    target_thread = self.topics.get("normal") or fallback_thread
                    route_reason = f"route='{route}' -> normal"

                elif route in ("member", "membership"):
                    target_thread = self.topics.get("member") or fallback_thread
                    route_reason = f"route='{route}' -> member"

                else:
                    # ไม่มี route -> route จาก timeframe
                    tf = (timeframe or "").lower().strip()
                    if tf in ("1d", "1day", "d"):
                        target_thread = self.topics.get("vip") or fallback_thread
                        route_reason = f"timeframe='{tf}' -> vip"
                    elif tf in ("15m", "15min", "m15"):
                        target_thread = self.topics.get("15m") or self.topics.get("chat") or fallback_thread
                        route_reason = f"timeframe='{tf}' -> 15m"
                    else:
                        target_thread = fallback_thread
                        route_reason = f"timeframe='{tf}' -> normal(fallback)"

            if os.getenv("DEBUG_TELEGRAM_ROUTE") == "1":
                logger.info(f"[ROUTE] symbol={symbol} tf={timeframe} route={route or '-'} -> thread={target_thread} ({route_reason})")


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
                f"{'🟢🚀 LONG SIGNAL' if is_long else '🔴📉 SHORT SIGNAL'}\n\n"
                f"🧩 System: {system_name} | TF: {timeframe}\n"
                f"🪙 {symbol}\n\n"
                f"💰 Entry: {entry:,.4f}\n\n"
                f"🎯 TP1: {tp1:,.4f} ({tp1_pct:+.1f}%) {rr1:.1f}:1\n"
                f"🎯 TP2: {tp2:,.4f} ({tp2_pct:+.1f}%) {rr2:.1f}:1\n"
                f"🎯 TP3: {tp3:,.4f} ({tp3_pct:+.1f}%) {rr3:.1f}:1\n\n"
                f"🛑 STOP LOSS: {sl:,.4f} ({sl_pct:+.1f}%)\n\n"
                f"💪 Strength: {strength}%\n"
                f"🕐 {now_th}"
            )

            self.send_message(message, thread_id=target_thread)
            logger.info(f"Telegram signal sent: {symbol}")
        except Exception as e:
            logger.error(f"Telegram Alert Error: {e}")

    # =========================
    # ✅ TP/SL Alert (15m / 1D routing + Status ครบ)
    # =========================
    def send_tp_sl_alert(self, payload: Dict, topic_id: Optional[int] = None):
        try:
            symbol = payload.get("symbol", "UNKNOWN")
            timeframe = (payload.get("timeframe") or "15m").lower().strip()
            side = (payload.get("side") or "").upper().strip()
            system_name = payload.get("system_name") or "SYSTEM"

            entry = float(payload.get("entry", 0) or 0)
            tp_levels = payload.get("tp_levels") or {}
            sl_level = float(payload.get("sl_level", 0) or 0)

            tp_hit = payload.get("tp_hit") or {}
            sl_hit = bool(payload.get("sl_hit", False))
            event = (payload.get("event") or "").upper().strip()

            now_th = datetime.now(ZoneInfo("Asia/Bangkok")).strftime("%H:%M:%S")

            # Header
            header = f"🟢✅ TAKE PROFIT {event}" if event.startswith("TP") else "🔴🛑 STOP LOSS"

            # Marks
            def _mark_tp(k: str) -> str:
                return "✅" if bool(tp_hit.get(k)) else "⬜️"

            def _mark_sl() -> str:
                return "❌" if (sl_hit or event == "SL") else "⬜️"

            tp1 = float(tp_levels.get("TP1", 0) or 0)
            tp2 = float(tp_levels.get("TP2", 0) or 0)
            tp3 = float(tp_levels.get("TP3", 0) or 0)

            message = (
                f"{header}\n\n"
                f"🧩 System: {system_name} | TF: {timeframe}\n"
                f"🪙 {symbol} | {side}\n\n"
                f"💰 Entry: {entry:,.4f}\n\n"
                f"Status:\n"
                f"{_mark_tp('TP1')} TP1: {tp1:,.4f}\n"
                f"{_mark_tp('TP2')} TP2: {tp2:,.4f}\n"
                f"{_mark_tp('TP3')} TP3: {tp3:,.4f}\n"
                f"{_mark_sl()} SL : {sl_level:,.4f}\n\n"
                f"🕐 {now_th}"
            )

            # ✅ Routing: TP/SL ทุก TF ไปห้อง แจ้ง TP SL (TOPIC_CHAT_ID)
            thread = self.topics.get("chat") or self.topics.get("normal")

            if thread:
                self.send_message(message, thread_id=int(thread))
            else:
                self.send_message(message)
                            
        except Exception as e:
            logger.error(f"TP/SL Alert Error: {e}")

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
