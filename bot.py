import os
import time
import threading
import random
import requests
from flask import Flask, request
import telebot

# ===========================
# إعداد المتغيرات
# ===========================
BOT_TOKEN = os.getenv("BOT_TOKEN")       # مفتاح البوت تليجرام
GEMINI_KEY = os.getenv("GEMINI_KEY")     # مفتاح GeminiGen AI
CHANNEL_ID = os.getenv("CHANNEL_ID")     # chat.id للقناة (مثلاً -1001234567890)
WEBHOOK_URL = os.getenv("WEBHOOK_URL")   # رابط الخدمة Render

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ===========================
# قائمة المطالبات العشوائية
# ===========================
def get_random_prompt():
    prompts = [
        "A funny Gulf joke video, speak in Arabic, humorous acting",
        "A funny Egyptian skit video, speak in Arabic, comic gestures",
        "A Syrian joke video with creative acting, Arabic dialogue",
        "A short comedy clip, people acting funny, Arabic humor",
        "A prank or silly scene, Arabic voices, funny reactions"
    ]
    return random.choice(prompts)

# ===========================
# دالة إنشاء فيديو عن طريق GeminiGen
# ===========================
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
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        video_url = result.get("video_url")  # تحقق من الوثائق الدقيقة
        return video_url
    except Exception as e:
        print("❌ حدث خطأ أثناء إنشاء الفيديو:", e)
        return None

# ===========================
# دالة إرسال الفيديو للتلجرام
# ===========================
def send_video_to_telegram(video_url):
    if video_url:
        try:
            bot.send_message(CHANNEL_ID, "🎬 فيديو مضحك جديد جاهز!")
            bot.send_video(CHANNEL_ID, video_url)
            print("✅ تم إرسال الفيديو للتلجرام")
        except Exception as e:
            print("❌ حدث خطأ أثناء إرسال الفيديو للتلجرام:", e)

# ===========================
# دالة الجدولة كل 5 دقائق
# ===========================
def schedule_videos():
    while True:
        prompt_text = get_random_prompt()
        print("⏳ جاري إنشاء الفيديو...")
        video_url = create_video(prompt_text)
        send_video_to_telegram(video_url)
        time.sleep(300)  # 5 دقائق = 300 ثانية

# ===========================
# Webhook endpoint
# ===========================
@app.route('/', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

# ===========================
# بدء الخادم + جدولة الفيديو
# ===========================
if __name__ == "__main__":
    # إزالة أي Webhook قديم
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)

    # تشغيل الجدولة في Thread منفصل
    video_thread = threading.Thread(target=schedule_videos)
    video_thread.daemon = True
    video_thread.start()

    # تشغيل Flask
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
