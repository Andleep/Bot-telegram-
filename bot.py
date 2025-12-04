import os
import time
import requests
from flask import Flask, request
import telebot
from threading import Thread

# ----------- إعداد المتغيرات البيئية -----------
BOT_TOKEN = os.getenv("BOT_TOKEN")           # توكن البوت من BotFather
CHANNEL_ID = os.getenv("CHANNEL_ID")         # معرف القناة: -100xxxxxxxxxx
GEMINI_KEY = os.getenv("GEMINI_KEY")         # مفتاح GeminiGen AI
WEBHOOK_URL = os.getenv("WEBHOOK_URL")       # رابط Webhook العام: https://yourrenderurl.com/<BOT_TOKEN>

# تحقق من وجود كل المتغيرات
if not all([BOT_TOKEN, CHANNEL_ID, GEMINI_KEY, WEBHOOK_URL]):
    print("❌ خطأ: تأكد من ضبط جميع المتغيرات البيئة BOT_TOKEN, CHANNEL_ID, GEMINI_KEY, WEBHOOK_URL")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ----------- دالة إنشاء الفيديو عن طريق GeminiGen AI -----------
def create_video(prompt_ar, duration=10):
    """
    prompt_ar: النص العربي الذي تريد تحويله إلى فيديو
    duration: مدة الفيديو بالثواني
    """
    prompt_en = f"Funny video: {prompt_ar}"  # مطالبة بالإنجليزية
    url = "https://api.geminigen.ai/api/v1/video/generate"  # رابط API الجديد
    headers = {
        "x-api-key": GEMINI_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "type": "video",
        "prompt": prompt_en,
        "duration": duration
    }
    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        result = response.json()
        # استخرج رابط الفيديو الناتج
        video_url = result.get("url") or result.get("video_url")
        return video_url
    except Exception as e:
        print(f"❌ حدث خطأ أثناء إنشاء الفيديو: {e}")
        return None

# ----------- دالة إرسال الفيديو للقناة -----------
def send_video_to_channel(video_url):
    if video_url:
        try:
            bot.send_video(CHANNEL_ID, video_url)
            print(f"✅ تم إرسال الفيديو: {video_url}")
        except Exception as e:
            print(f"❌ خطأ أثناء الإرسال للقناة: {e}")
    else:
        print("❌ لا يوجد فيديو للإرسال")

# ----------- دالة تشغيل الفيديو كل 5 دقائق -----------
def video_scheduler():
    while True:
        prompt = "فاصل كوميدي خليجي مضحك"  # يمكن تغييره عشوائي لاحقًا
        print(f"⏳ جاري إنشاء الفيديو بعنوان: {prompt}")
        video = create_video(prompt, duration=10)
        send_video_to_channel(video)
        print("⏰ انتظار 5 دقائق قبل إنشاء الفيديو التالي...")
        time.sleep(300)  # 5 دقائق

# ----------- Webhook لـ Telegram -----------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "", 200

# ----------- أوامر البوت -----------
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "مرحبًا! البوت جاهز لإرسال الفيديوهات تلقائيًا 🎬")

# ----------- تشغيل Webhook على Render -----------
def start_bot():
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    Thread(target=video_scheduler).start()
    print("🚀 البوت يعمل وجاهز")

# ----------- نقطة البداية ----------- 
if __name__ == "__main__":
    start_bot()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
