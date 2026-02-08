from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, TextMessage, PushMessageRequest

# LINE Config
LINE_TOKEN = "YCvky4EDwOvZmzyw9ChiYpBLY4MvFqZZ+a9vC2Nt5mhhw3UQoRUQSw/hJIjtWoxtxnoOLHRevaI9g3sxhNpQlyW5Xkdhw51/jwVAVoPGhoFPUz8Xz9HfxJYRWQNr0YvTXhFoJlxe1+lNbnTUGBGzRgdB04t89/1O/w1cDnyilFU="
LINE_USER_ID = "Uc6abb9a104a3bc78e6627150c62fb962"

# Test message
message = """━━━━━━━━━━━━━━━━━
🟡⚡ REBOUND ALERT ⚡🟡
━━━━━━━━━━━━━━━━━

📊 Strategy: 15m SCALP
🪙 BTCUSDT - LONG 📈

💵 Entry: 69,200.00
🛑 SL: 68,854.00 (-0.5%)

🎯 TP1: 69,892.00 (+1.0%) [2:1]
🎯 TP2: 70,584.00 (+2.0%) [4:1]
🎯 TP3: 71,276.00 (+3.0%) [6:1]

📊 RSI: 32.5 (Oversold)
📈 Volume: 2.3x

⚠️ Quick Scalp - Exit Fast!
🕐 20:30:00

🤖 SIGNAL-ALERT v2.2 (TEST)
━━━━━━━━━━━━━━━━━"""

try:
    configuration = Configuration(access_token=LINE_TOKEN)
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.push_message(
            PushMessageRequest(
                to=LINE_USER_ID,
                messages=[TextMessage(text=message)]
            )
        )
    print("✅ ส่ง LINE ทดสอบสำเร็จ!")
except Exception as e:
    print(f"❌ Error: {e}")
