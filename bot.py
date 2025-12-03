import os
import time
import threading
import telebot
from flask import Flask, request, abort
import requests

# --- الإعدادات ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # chat_id أو @اسم_القناة
GEMINI_KEY = os.getenv("GEMINI_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # رابط Render مع /

if not all([BOT_TOKEN, CHANNEL_ID, GEMINI_KEY, WEBHOOK_URL]):
    print("❌ خطأ: تأكد من ضبط جميع المتغيرات البيئة BOT_TOKEN, CHANNEL_ID, GEMINI_KEY, WEBHOOK_URL")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- دالة إنشاء الفيديو ---
def create_video(prompt_text):
    print(f"⏳ جاري إنشاء الفيديو بعنوان: {prompt_text}")
    url = "https://api.geminigen.ai/uapi/v1/generate"
    headers = {
        "x-api-key": GEMINI_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "type": "video",
        "prompt": prompt_text,
        "language": "ar"  # الكلام بالعربي داخل الفيديو
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        video_url = data.get("video_url") or data.get("url")  # حسب رد API
        if video_url:
            print(f"✅ تم إنشاء الفيديو: {video_url}")
            return video_url
        else:
            print("❌ لم يتم إنشاء الفيديو. استجابة API:", data)
            return None
    except Exception as e:
        print("❌ حدث خطأ أثناء إنشاء الفيديو:", e)
        return None

# --- دالة إرسال الفيديو للقناة ---
def send_video_to_channel(video_url):
    if not video_url:
        print("❌ لا يوجد فيديو للإرسال")
        return
    try:
        bot.send_message(CHANNEL_ID, f"🎬 فيديو جديد: {video_url}")
        print(f"✅ تم إرسال الفيديو للقناة: {CHANNEL_ID}")
    except Exception as e:
        print("❌ حدث خطأ أثناء إرسال الفيديو:", e)

# --- دالة المهام الدورية ---
def job():
    prompts = [
        "فاصل كوميدي خليجي مضحك",
        "تمثيل مضحك مصري",
        "نكثة سورية مضحكة",
        "مقطع مضحك خليجي عشوائي",
        "تمثيل هزلي مصري"
    ]
    while True:
        prompt = prompts[int(time.time()) % len(prompts)]  # اختيار عشوائي مبسط
        video_url = create_video(prompt)
        send_video_to_channel(video_url)
        print("⏰ انتظار 5 دقائق قبل إنشاء الفيديو التالي...")
        time.sleep(300)  # 5 دقائق

# --- بوت التلجرام ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "مرحبًا! البوت جاهز لإرسال الفيديوهات تلقائيًا 🎬")

# --- Webhook (لـ Render) ---
@app.route("/", methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_str = request.get_data().decode('UTF-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return ""
    else:
        abort(403)

# --- تشغيل المهمة الدورية في Thread ---
threading.Thread(target=job, daemon=True).start()

# --- ضبط Webhook على Telegram ---
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

# --- تشغيل Flask ---
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    print(f"🚀 البوت يعمل على المنفذ {port}")
    app.run(host="0.0.0.0", port=port)
