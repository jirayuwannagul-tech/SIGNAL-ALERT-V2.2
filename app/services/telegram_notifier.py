import logging
import requests
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Optional
logger = logging.getLogger(__name__)

def _to_int(v):
    try:
        return int(v) if v is not None and str(v).strip() != "" else None
    except:
        return None

class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.topics = {
            "normal": int(os.getenv("TOPIC_NORMAL_ID", "2")),
            "vip": int(os.getenv("TOPIC_VIP_ID", "18")),
            "chat": int(os.getenv("TOPIC_CHAT_ID", "1")),
            "15m": int(os.getenv("TOPIC_15M_ID", "249")),
            "member": int(os.getenv("TOPIC_MEMBER_ID", "4")),
        }
        logger.info(f"TelegramNotifier ready | topics={self.topics}")

    def resolve_topic_id(self, timeframe: str, fallback: Optional[int] = None) -> Optional[int]:
        tf = (timeframe or "").lower().strip()
        if tf in ("1d", "1day", "d"):
            return self.topics.get("vip") or fallback
        if tf in ("15m", "15min", "m15"):
            return self.topics.get("15m") or fallback
        return fallback

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

    def send_membership_alert(self, text: str):
        self.send_message(text, thread_id=self.topics["member"])

    def send_direct_message(self, user_id: str, text: str):
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {"chat_id": user_id, "text": text, "parse_mode": "Markdown"}
            requests.post(url, json=payload, timeout=10)
        except:
            pass
