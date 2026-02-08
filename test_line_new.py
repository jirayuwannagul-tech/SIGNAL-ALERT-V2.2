from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, TextMessage, PushMessageRequest

LINE_TOKEN = "LGtMMdUh0U36cC1alF7b9gJDQJy6vetK29bX532zvhxbokiAkYYTlR8AWK9hfiOYxnoOLHRevaI9g3sxhNpQlyW5Xkdhw51/jwVAVoPGhoHe8WqNMKQYPHPQLHYQF4o46GoaMNCRnM2k6IeElx7rWQdB04t89/1O/w1cDnyilFU="
LINE_USER_ID = "Uc6abb9a104a3bc78e6627150c62fb962"

message = """🎉 ทดสอบ LINE Token ใหม่

🤖 SIGNAL-ALERT v2.2
✅ Token ใช้งานได้!"""

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
    print("✅ ส่ง LINE สำเร็จ! เช็ค LINE ของคุณ")
except Exception as e:
    print(f"❌ Error: {e}")
