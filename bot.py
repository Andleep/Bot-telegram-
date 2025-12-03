# bot.py
import os
import time
import requests
import telebot
from flask import Flask, request, abort

# --- ضبط المتغيرات من Environment ---
BOT_TOKEN = os.getenv("BOT_TOKEN")          # توكن البوت من BotFather
CHANNEL_ID = os.getenv("CHANNEL_ID")        # @اسم_القناة أو chat_id
GEMINI_KEY = os.getenv("GEMINI_KEY")        # مفتاح GeminiGen
WEBHOOK_URL = os.getenv("WEBHOOK_URL")      # رابط Render + /webhook

if not all([BOT_TOKEN, CHANNEL_ID, GEMINI_KEY, WEBHOOK_URL]):
    print("❌ خطأ: تأكد من ضبط جميع المتغيرات البيئة BOT_TOKEN, CHANNEL_ID, GEMINI_KEY, WEBHOOK_URL")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

VIDEO_PROMPTS = [
    "فاصل كوميدي خليجي مضحك",
    "تمثيل مضحك مصري",
    "نكث سورية مضحك",
    "مواقف كوميدية خليجية",
    "مقاطع مضحكة قصيرة"
]

# --- إنشاء فيديو عبر GeminiGen ---
def create_video(prompt):
    url = "https://api.geminigen.ai/uapi/v1/video/generate"
    headers = {
        "x-api-key": GEMINI_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "prompt": prompt,
        "duration": 10,
        "type": "video",
        "voice": "arabic"
    }
    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        result = response.json()
        # نفترض أن الرابط النهائي للفيديو يكون في result['video_url']
        return result.get("video_url")
    except Exception as e:
        print(f"❌ حدث خطأ أثناء إنشاء الفيديو: {e}")
        return None

# --- إرسال الفيديو للتلجرام ---
def send_video(video_url):
    if video_url:
        bot.send_video(CHANNEL_ID, video_url)
        print("✅ تم إرسال الفيديو بنجاح")
    else:
        print("❌ لا يوجد فيديو للإرسال")

# --- مهمة دورية ---
def video_loop():
    while True:
        prompt = VIDEO_PROMPTS[int(time.time()) % len(VIDEO_PROMPTS)]  # اختيار عشوائي مبسط
        print(f"⏳ جاري إنشاء الفيديو بعنوان: {prompt}")
        video_url = create_video(prompt)
        send_video(video_url)
        print("⏰ انتظار 5 دقائق قبل إنشاء الفيديو التالي...")
        time.sleep(5 * 60)

# --- بوت التلجرام ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "مرحبًا! البوت جاهز لإرسال الفيديوهات تلقائيًا 🎬")

# --- Webhook ---
@app.route("/webhook", methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        json_str = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return "", 200
    else:
        abort(403)

# --- بدء Flask و Webhook ---
if __name__ == "__main__":
    # تعيين Webhook
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    print("🚀 البوت يعمل بنجاح على Webhook")

    # تشغيل حلقة الفيديو في الخلفية
    import threading
    t = threading.Thread(target=video_loop)
    t.start()

    # تشغيل Flask
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
