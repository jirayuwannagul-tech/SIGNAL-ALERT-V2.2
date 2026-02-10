import requests
import os
from dotenv import load_dotenv

# โหลดค่าจากไฟล์ .env
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = "-1003744942992"  # ใส่ ID ที่เราสรุปกันไว้

# รายการห้องที่ต้องการทดสอบ
topics = {
    "1": "ห้อง General (พูดคุยหลัก)",
    "2": "ห้อง [FREE] สัญญาณทั่วไป",
    "3": "ห้อง [VIP] SIGNAL",
    "4": "ห้อง สมัครสมาชิก"
}

def test_send():
    print(f"🚀 เริ่มการทดสอบส่งข้อความ Telegram...")
    
    for thread_id, room_name in topics.items():
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": f"🤖 **บอทจำเฉย v2.2 Test**\n✅ ทดสอบส่งเข้า: {room_name}\n📍 Thread ID: {thread_id}",
            "message_thread_id": thread_id,
            "parse_mode": "Markdown"
        }
        
        try:
            res = requests.post(url, json=payload)
            if res.json().get("ok"):
                print(f"✅ ส่งเข้า {room_name} สำเร็จ!")
            else:
                print(f"❌ {room_name} ล้มเหลว: {res.json().get('description')}")
        except Exception as e:
            print(f"❗ เกิดข้อผิดพลาดที่ {room_name}: {e}")

if __name__ == "__main__":
    test_send()