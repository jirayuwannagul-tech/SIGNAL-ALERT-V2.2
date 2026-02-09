import logging
import requests
from typing import Dict

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        logger.info("บอทจำเฉย (Telegram) เชื่อมต่อระบบภาษาไทยเรียบร้อย")

    def send_message(self, text: str):
        """ส่งข้อความทั่วไป"""
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}
            response = requests.post(url, json=payload)
            return response.json()
        except Exception as e:
            logger.error(f"ส่งข้อความ Telegram ไม่สำเร็จ: {e}")

    def send_signal_alert(self, signal: Dict):
        """ส่งสัญญาณเทรดแบบภาษาไทย"""
        try:
            symbol = signal.get("symbol", "ไม่ระบุเหรียญ")
            side = "🟢 LONG" if "LONG" in str(signal) else "🔴 SHORT"
            strength = signal.get("signal_strength", 0)
            
            message = (
                f"🚀 *พบสัญญาณใหม่!*\n\n"
                f"เหรียญ: `{symbol}`\n"
                f"ทิศทาง: {side}\n"
                f"ความแรง: `{strength}%`\n"
                f"สถานะ: บอทเปิดออเดอร์ให้แล้วครับพี่!"
            )
            self.send_message(message)
        except Exception as e:
            logger.error(f"ส่ง Signal Alert ไม่สำเร็จ: {e}")