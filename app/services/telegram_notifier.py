import logging
import requests
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id

    def send_signal_alert(self, analysis: Dict) -> bool:
        if not self.token or not self.chat_id:
            logger.warning("⚠️ Telegram config missing")
            return False
            
        timeframe = analysis.get("timeframe", "4h")
        if timeframe == "1d":
            alert_title = "CDC TREND ALERT"
        elif timeframe == "4h":
            alert_title = "SQUEEZE BREAKOUT"
        else:
            alert_title = "QUICK REBOUND"

        message = self._create_message(analysis, alert_title)
        
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {"chat_id": self.chat_id, "text": message}
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info("✅ Telegram alert sent")
                return True
            else:
                logger.error(f"❌ Telegram API Error: {response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ Telegram Exception: {e}")
            return False

    def _create_message(self, analysis: Dict, alert_title: str) -> str:
        symbol = analysis.get('symbol', 'Unknown')
        direction = analysis.get('direction', 'Unknown')
        entry = analysis.get('entry_price', 0)
        sl = analysis.get('sl_price', 0)
        tp_list = analysis.get('tp_targets', [])
        
        header = "🔵⚡" if "CDC" in alert_title else "🟢⚡" if "SQUEEZE" in alert_title else "🟡⚡"
        direction_emoji = "🟢" if direction == "LONG" else "🔴"
        
        tp_text = "\n".join([f"🎯 TP{i+1}: {t.get('price', 0):,.2f}" for i, t in enumerate(tp_list)])

        return f"""{header} {alert_title} {header}
━━━━━━━━━━━━━━━━━
🪙 {symbol} - {direction} {direction_emoji}
💵 Entry: {entry:,.2f}
�� SL: {sl:,.2f}
{tp_text}
🕐 {datetime.now().strftime('%H:%M:%S')}
🤖 v2.2 Telegram Exclusive
━━━━━━━━━━━━━━━━━"""
