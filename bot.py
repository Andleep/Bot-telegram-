import os
import time
import threading
import requests
from flask import Flask, request
import telebot
import random

# ======================
# إعداد المتغيرات من Environment Variables
# ======================
BOT_TOKEN = os.getenv("BOT_TOKEN")        # مفتاح بوت Telegram
CHANNEL_ID = os.getenv("CHANNEL_ID")      # مثال: -1001234567890
GEMINI_KEY = os.getenv("GEMINI_KEY")      # مفتاح GeminiGen
WEBHOOK_URL = os.getenv("WEBHOOK_URL")    # رابط Render + /

# ======================
# تهيئة البوت و Flask
# ======================
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ======================
# أوامر البوت
# ======================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "مرحبًا! البوت يعمل وسيقوم بإرسال فيديوهات مضحكة كل 5 دقائق للقناة.")

# ======================
# Webhook route
# ======================
@app.route("/", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "!", 200

# ======================
# إنشاء فيديو مضحك من GeminiGen AI
# ======================
def create_funny_video():
    if not GEMINI_KEY:
        print("❌ GEMINI_KEY غير موجود")
        return None

    prompts = [
        "نكث خليجي مضحك",
        "تمثيل كوميدي مصري",
        "موقف مضحك عائلي عربي",
        "نكث سوري مضحك"
    ]
    prompt = random.choice(prompts)

    headers = {
        "x-api-key": GEMINI_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "type": "video",
        "prompt": f"Create a funny short video: {prompt} (الكلام بالعربي)"
    }

    try:
        response = requests.post("https://api.geminigen.ai/uapi/v1/generate", json=data, headers=headers)
        response.raise_for_status()
        result = response.json()
        video_url = result.get("url")
        print(f"✅ تم إنشاء الفيديو: {video_url}")
        return video_url
    except Exception as e:
        print(f"❌ خطأ أثناء إنشاء الفيديو: {e}")
        return None

# ======================
# إرسال الفيديو للقناة
# ======================
def send_video_to_channel(video_url):
    try:
        bot.send_video(CHANNEL_ID, video_url)
        print(f"✅ تم إرسال الفيديو للقناة: {video_url}")
    except Exception as e:
        print(f"❌ خطأ أثناء إرسال الفيديو للقناة: {e}")

# ======================
# Thread لإرسال فيديو كل 5 دقائق
# ======================
def scheduled_videos():
    while True:
        video = create_funny_video()
        if video:
            send_video_to_channel(video)
        time.sleep(300)  # كل 5 دقائق

# ======================
# بدء Thread عند التشغيل
# ======================
threading.Thread(target=scheduled_videos, daemon=True).start()

# ======================
# تسجيل Webhook تلقائيًا عند تشغيل Render
# ======================
@app.before_first_request
def setup_webhook():
    if not WEBHOOK_URL:
        print("❌ WEBHOOK_URL غير محدد")
        return
    try:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        print(f"✅ تم تسجيل Webhook: {WEBHOOK_URL}")
    except Exception as e:
        print(f"❌ خطأ أثناء تسجيل Webhook: {e}")

# ======================
# تشغيل Flask
# ======================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
