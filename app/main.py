import requests
from flask import Flask, request, jsonify
# ... (ส่วน import อื่นๆ ของพี่ที่มีอยู่เดิม) ...

@app.route('/api/telegram/webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({"status": "no message"}), 200

    message = data['message']
    text = message.get('text', '')
    chat_id = str(message.get('chat', {}).get('id', ''))
    
    # 🔐 ดึง Chat ID ที่อนุญาตจาก Railway Variables อัตโนมัติ
    authorized_id = services["config_manager"].get("telegram_chat_id")
    
    if str(chat_id).strip() != str(authorized_id).strip():
        logger.warning(f"⚠️ มีคนแปลกหน้าพยายามสั่งบอท! ID: {chat_id}")
        return jsonify({"status": "unauthorized"}), 200

    # 🤖 ดึง Token มาเตรียมยิงตรง
    bot_token = services["config_manager"].get("telegram_bot_token")
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    if text == "/status":
        summary = services["position_manager"].get_positions_summary() if services["position_manager"] else {}
        active = summary.get("active_positions", 0)
        msg = (
            f"🤖 *รายงานตัวครับพี่!*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"✅ สถานะ: บอทจำเฉยบ้านใหม่พร้อมรบ\n"
            f"📦 ถืออยู่: {active} ไม้\n"
            f"━━━━━━━━━━━━━━━\n"
            f"สั่งสแกนพิมพ์ /scan ได้เลยครับ"
        )
        requests.post(api_url, json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})

    elif text == "/scan":
        requests.post(api_url, json={"chat_id": chat_id, "text": "🔍 *รับทราบครับ!* กำลังออกไปควานหาเหรียญสวยๆ ให้พี่...", "parse_mode": "Markdown"})
        if services["scheduler"]:
            from threading import Thread
            Thread(target=services["scheduler"]._scan_4h_signals).start()

    return jsonify({"status": "ok"}), 200

# ... (ส่วนล่างของไฟล์พี่) ...
