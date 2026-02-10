import logging
import requests
import os
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        
        # 🌐 LAYER 0: Topic Configuration (ดึงค่าจาก Config/Env)
        self.topics = {
            "normal": os.getenv("TOPIC_NORMAL_ID"),   # ห้องสัญญาณธรรมดา
            "vip": os.getenv("TOPIC_VIP_ID"),         # ห้องสัญญาณ VIP
            "chat": os.getenv("TOPIC_CHAT_ID"),       # ห้องพูดคุย
            "member": os.getenv("TOPIC_MEMBER_ID")    # ห้องสมัครสมาชิก
        }
        logger.info("บอทจำเฉย (Telegram) v2.2 - ระบบแยกห้องและจัดการสมาชิกเปิดใช้งาน")

    # ================================================================
    # 🛰️ LAYER 1: Core API Methods (ฟังก์ชันพื้นฐานการส่ง)
    # ================================================================

    def send_message(self, text: str, thread_id: Optional[str] = None):
        """ส่งข้อความทั่วไป รองรับการแยก Topic ผ่าน thread_id"""
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id, 
                "text": text, 
                "parse_mode": "Markdown",
                "message_thread_id": thread_id, # 🎯 ระบุ ID ห้องย่อย
                "disable_web_page_preview": True
            }
            response = requests.post(url, json=payload, timeout=10)
            return response.json()
        except Exception as e:
            logger.error(f"Telegram Send Error: {e}")

    def kick_chat_member(self, chat_id: str, user_id: str):
        """คำสั่งเตะสมาชิกออกจากกลุ่ม (ใช้เมื่อหมดอายุ VIP)"""
        try:
            url = f"{self.api_url}/banChatMember" # ใน API ใหม่ใช้ ban เพื่อเตะออก
            payload = {"chat_id": chat_id, "user_id": user_id}
            response = requests.post(url, json=payload, timeout=10)
            # ปลดแบนทันทีเพื่อให้กลับเข้ามาห้องธรรมดาได้ (แต่จะหลุดจากกลุ่มปัจจุบัน)
            requests.post(f"{self.api_url}/unbanChatMember", json=payload)
            return response.json().get("ok", False)
        except Exception as e:
            logger.error(f"Telegram Kick Error: {e}")
            return False

    # ================================================================
    # 📢 LAYER 2: Signal Alerts (ส่วนพ่นสัญญาณเทรด - โค้ดเดิมของคุณ)
    # ================================================================

    def send_signal_alert(self, analysis: Dict, topic_id: str = None):
        """พ่นสัญญาณเทรดหน้าตาเดียวกับ LINE (แยกห้อง Spot/Futures)"""
        try:
            symbol = analysis.get("symbol", "UNKNOWN")
            timeframe = analysis.get("timeframe", "4h")
            current_price = analysis.get("current_price", 0)
            signals = analysis.get("signals", {})
            risk = analysis.get("risk_levels", {})
            strength = analysis.get("signal_strength", 0)

            # 🎯 ดิจิทัลเลือกห้อง: 
            # ถ้าเป็น Futures (ใช้โค้ดเดิมที่ทำไว้) ส่งเข้าห้อง VIP
            # ถ้าเป็น Spot (ในอนาคต) ส่งเข้าห้องธรรมดา
            # ปัจจุบันกำหนดให้ Futures ทั้งหมดเข้า VIP ตามที่คุณแจ้ง
            target_thread = topic_id or self.topics["vip"]

            # ดึงค่า Risk Levels
            entry = risk.get('entry_price', current_price)
            sl = risk.get('stop_loss', 0)
            tp1 = risk.get('take_profit_1', 0)
            tp2 = risk.get('take_profit_2', 0)
            tp3 = risk.get('take_profit_3', 0)

            # ตั้งค่า Emoji และทิศทาง (โค้ดเดิม)
            if signals.get("buy"):
                direction, emoji, header_emoji = "LONG", "🟢", "🟢⚡ SQUEEZE ALERT ⚡🟢"
                sl_pct = ((sl - entry) / entry) * 100 if entry != 0 else 0
                tp1_pct = ((tp1 - entry) / entry) * 100 if entry != 0 else 0
                tp2_pct = ((tp2 - entry) / entry) * 100 if entry != 0 else 0
                tp3_pct = ((tp3 - entry) / entry) * 100 if entry != 0 else 0
            else:
                direction, emoji, header_emoji = "SHORT", "🔴", "🔴⚡ SQUEEZE ALERT ⚡🔴"
                sl_pct = ((sl - entry) / entry) * 100 if entry != 0 else 0
                tp1_pct = -((entry - tp1) / entry) * 100 if entry != 0 else 0
                tp2_pct = -((entry - tp2) / entry) * 100 if entry != 0 else 0
                tp3_pct = -((entry - tp3) / entry) * 100 if entry != 0 else 0

            rr1 = abs(tp1_pct / sl_pct) if sl_pct != 0 else 0
            rr2 = abs(tp2_pct / sl_pct) if sl_pct != 0 else 0
            rr3 = abs(tp3_pct / sl_pct) if sl_pct != 0 else 0

            if timeframe == "1d": header_emoji = "🔵⚡ CDC ALERT ⚡🔵"
            elif timeframe == "15m": header_emoji = "🟡⚡ REBOUND ALERT ⚡🟡"

            # ประกอบร่างข้อความ (Markdown Style)
            message = (
                f"{header_emoji}\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"📊 *Strategy:* `{timeframe.upper()} SWING`\n"
                f"🪙 *{symbol}* - {direction} {emoji}\n"
                f"💵 *Entry:* `{entry:,.2f}`\n"
                f"🛑 *SL:* `{sl:,.2f}` ({sl_pct:+.1f}%)\n"
                f"🎯 *TP1:* `{tp1:,.2f}` ({tp1_pct:+.1f}%) [{rr1:.1f}:1]\n"
                f"🎯 *TP2:* `{tp2:,.2f}` ({tp2_pct:+.1f}%) [{rr2:.1f}:1]\n"
                f"🎯 *TP3:* `{tp3:,.2f}` ({tp3_pct:+.1f}%) [{rr3:.1f}:1]\n"
                f"💪 *Strength:* `{strength}%`\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"🕐 `{datetime.now().strftime('%H:%M:%S')}`\n"
                f"🤖 *SIGNAL-ALERT v2.2*"
            )
            
            # ส่งไปที่ห้องที่กำหนด
            self.send_message(message, thread_id=target_thread)
            logger.info(f"✅ [Telegram] พ่นซิกเข้าห้อง VIP เรียบร้อย: {symbol}")
            
        except Exception as e:
            logger.error(f"❌ Telegram Alert Error: {e}")

    # ================================================================
    # 💳 LAYER 3: Membership Notifications (แจ้งเตือนสถานะสมาชิก)
    # ================================================================

    def send_membership_alert(self, text: str):
        """ส่งข้อความเข้าห้อง 'สมัครสมาชิก' โดยเฉพาะ"""
        self.send_message(text, thread_id=self.topics["member"])

    def send_direct_message(self, user_id: str, text: str):
        """ส่งข้อความหา User ส่วนตัว (ถ้า User เคยทักบอทไว้)"""
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {"chat_id": user_id, "text": text, "parse_mode": "Markdown"}
            requests.post(url, json=payload, timeout=10)
        except:
            pass