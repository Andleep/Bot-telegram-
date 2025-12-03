import os
import time
import threading
from flask import Flask, request
import telebot
import requests

# =============================
# إعدادات البوت والمتغيرات
# =============================
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # ضع مفتاح بوت Telegram هنا
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # رابط Render مع / في النهاية
CHANNEL_ID = os.environ.get("CHANNEL_ID")  # @اسم_القناة أو chat_id

GEMINI_KEY = os.environ.get("GEMINI_KEY")  # مفتاح GeminiGen AI

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# =============================
# أوامر البوت
# =============================
@bot.message_handler(commands=['start'])
def start_message(message):
    bot.reply_to(message, "مرحبًا! البوت جاهز لإرسال الفيديوهات تلقائيًا 🎬")

# =============================
# دالة لإنشاء فيديو عبر GeminiGen AI
# =============================
def create_video(prompt_text):
    url = "https://api.geminigen.ai/uapi/v1/generate"
    headers = {
        "x-api-key": GEMINI_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "type": "video",
        "prompt": prompt_text
    }
    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        result = response.json()
        # افترض أن الرابط النهائي للفيديو موجود في result['url']
        return result.get("url", None)
    except Exception as e:
        print("❌ خطأ أثناء إنشاء الفيديو:", e)
        return None

# =============================
# دالة إرسال الفيديو للقناة
# =============================
def send_video_to_channel(video_url):
    if video_url:
        try:
            bot.send_video(CHANNEL_ID, video=video_url)
            print("✅ تم إرسال الفيديو للقناة")
        except Exception as e:
            print("❌ خطأ أثناء إرسال الفيديو:", e)

# =============================
# دالة تعمل بشكل دوري كل 5 دقائق
# =============================
def periodic_video_task():
    while True:
        try:
            # يمكنك تغيير النصوص لتكون عشوائية: خليجي، مصري، نكث، تمثيل مضحك
            prompts = [
                "فاصل كوميدي خليجي مضحك",
                "موقف تمثيلي مصري مضحك",
                "نكث سورية كوميديا خفيفة"
            ]
            prompt = prompts[int(time.time()) // 300 % len(prompts)]  # كل 5 دقائق نص جديد
            print("⏳ جاري إنشاء الفيديو:", prompt)
            video_url = create_video(prompt)
            send_video_to_channel(video_url)
        except Exception as e:
            print("❌ خطأ في المهمة الدورية:", e)
        time.sleep(300)  # 5 دقائق

# =============================
# Webhook: استقبال تحديثات Telegram
# =============================
@app.route("/", methods=["POST"])
def webhook():
    json_data = request.get_json()
    if json_data:
        update = telebot.types.Update.de_json(json_data)
        bot.process_new_updates([update])
    return "", 200

# =============================
# تسجيل Webhook وتشغيل Flask
# =============================
if __name__ == "__main__":
    try:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        print(f"✅ تم تسجيل Webhook: {WEBHOOK_URL}")
    except Exception as e:
        print("❌ خطأ أثناء تسجيل Webhook:", e)

    # تشغيل المهمة الدورية في Thread منفصل
    threading.Thread(target=periodic_video_task, daemon=True).start()

    # تشغيل Flask
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
