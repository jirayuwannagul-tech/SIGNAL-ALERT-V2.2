import requests
from flask import Flask, request, jsonify
import logging

app = Flask(__name__)
logger = logging.getLogger(__name__)

# บรรทัดที่พี่ต้องแก้เลขห้อง (ผมใส่เลขใหม่ให้แล้ว)
AUTHORIZED_CHAT_ID = "-5080904156"

@app.route('/api/telegram/webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({"status": "no message"}), 200

    message = data['message']
    text = message.get('text', '')
    chat_id = str(message.get('chat', {}).get('id', ''))
    
    # 🔐 เช็คสิทธิ์แบบเด็ดขาด
    if chat_id != AUTHORIZED_CHAT_ID:
        return jsonify({"status": "unauthorized"}), 200

    # 🤖 ดึง Token จาก Railway
    import os
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    if text == "/status":
        msg = "🤖 รายงานตัวครับพี่! บอทจำเฉยในห้องใหม่สแตนบายแล้วครับ"
        requests.post(api_url, json={"chat_id": chat_id, "text": msg})

    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
