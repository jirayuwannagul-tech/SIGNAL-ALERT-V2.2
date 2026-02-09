import requests
from flask import Flask, request, jsonify
import os, logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/api/telegram/webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({"status": "no message"}), 200

    message = data['message']
    text = message.get('text', '')
    chat_id = str(message.get('chat', {}).get('id', ''))
    
    # 🔐 ดึงเลขห้องจาก Variables ที่พี่เซตไว้
    authorized_id = os.getenv("TELEGRAM_CHAT_ID")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if chat_id.strip() != str(authorized_id).strip():
        logger.warning(f"Unauthorized ID: {chat_id}")
        return jsonify({"status": "unauthorized"}), 200

    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    if text == "/status":
        msg = "🤖 *รายงานตัวครับพี่!*\nบ้านใหม่เลขที่ " + chat_id + " พร้อมสแตนบายครับ"
        requests.post(api_url, json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})

    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    # รัน Flask บนพอร์ต 8080 ตามที่ Railway ต้องการ
    app.run(host='0.0.0.0', port=8080)
