import os
import time
import requests
import telebot
import logging
from flask import Flask
from threading import Thread

# ------------- إعداد السجلات ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# ------------- قراءة المتغيرات من البيئة ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_CHANNEL = os.getenv("BOT_CHANNEL")  # مثال: "@fawasil_comedy" أو "-1001234567890"
GEMINI_KEY = os.getenv("GEMINI_KEY")

# اختياري / لنشر لاحقاً
YOUTUBE_ACCESS_TOKEN = os.getenv("YOUTUBE_ACCESS_TOKEN", "")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN", "")

if not BOT_TOKEN:
    logging.error("BOT_TOKEN غير موجود في متغيرات البيئة. اضف BOT_TOKEN في Render ثم اعادة نشر.")
    raise SystemExit("Missing BOT_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# ------------- Flask لتجعل الخدمة تبقى "Web" حتى لا يطفئها Render -------------
app = Flask(__name__)

@app.route('/')
def index():
    return "Fawasil Comedy Bot — Running ✅"

def run_flask():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ------------- توليد Prompt بسيط (قابل للتعديل) -------------
def generate_prompt():
    prompts = [
        "A short 8-second funny Lebanese street party with dancing and playful greetings",
        "A comic scene: a clumsy chef slips but ends up making a delicious dish, 8s",
        "A dancing robot tries to imitate Dabke in a funny way, 8 seconds",
        "A short humorous scene: the phone rings and everyone thinks it's a ghost, 8 seconds",
        "A tiny story: a cat steals a sandwich and runs away with dramatic music, 8s"
    ]
    return f"Create a short 8-second video: {prompts[int(time.time()) % len(prompts)]}"

# ------------- استدعاء GeminiGen لتوليد فيديو -------------
def request_geminigen_video(prompt, timeout_sec=300, poll_interval=3):
    """
    Returns: local_file_path or raises Exception
    """
    if not GEMINI_KEY:
        raise Exception("GEMINI_KEY not set in environment variables.")
    headers = {
        "x-api-key": GEMINI_KEY,
        "Content-Type": "application/json"
    }
    payload = {"type": "video", "prompt": prompt}
    logging.info("Sending generate request to GeminiGen...")
    r = requests.post("https://api.geminigen.ai/uapi/v1/generate", json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    logging.info(f"GeminiGen response: {data}")

    video_url = data.get("video_url") or data.get("url")
    job_id = data.get("job_id")

    # إذا أعطانا رابط مباشرةً
    if video_url:
        return download_video_to_tmp(video_url)

    # إذا أعطانا job_id نعمل polling على الحالة
    if job_id:
        logging.info(f"Got job_id={job_id}, polling status...")
        elapsed = 0
        while elapsed < timeout_sec:
            status = requests.get(f"https://api.geminigen.ai/uapi/v1/status?job_id={job_id}", headers=headers, timeout=30)
            status.raise_for_status()
            st = status.json()
            logging.info(f"Status: {st}")
            video_url = st.get("video_url") or st.get("url")
            if video_url:
                return download_video_to_tmp(video_url)
            time.sleep(poll_interval)
            elapsed += poll_interval
        raise Exception("Timeout waiting for GeminiGen job to finish.")
    raise Exception("No video_url or job_id returned by GeminiGen.")

def download_video_to_tmp(video_url):
    logging.info(f"Downloading video from {video_url} ...")
    local_name = f"/tmp/video_{int(time.time())}.mp4"
    with requests.get(video_url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(local_name, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    logging.info(f"Saved video to {local_name}")
    return local_name

# ------------- إرسال الفيديو للقناة على Telegram -------------
def send_video_to_telegram_channel(file_path, caption="فاصل كوميدي جديد 😂"):
    logging.info(f"Sending {file_path} to Telegram channel {BOT_CHANNEL}")
    try:
        # telebot يمكنه استقبال مسار الملف مباشرة
        with open(file_path, "rb") as video:
            bot.send_video(chat_id=BOT_CHANNEL, data=video, caption=caption)
        logging.info("Uploaded to Telegram channel.")
    except Exception as e:
        logging.exception("Failed to send video to Telegram via telebot. Trying fallback via requests...")
        # Fallback: use direct HTTP multipart upload
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
        with open(file_path, "rb") as vid:
            files = {"video": vid}
            data = {"chat_id": BOT_CHANNEL, "caption": caption}
            r = requests.post(url, data=data, files=files, timeout=120)
            r.raise_for_status()
            logging.info("Uploaded via requests fallback.")

# ------------- أوامر البوت الأساسية -------------
@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.reply_to(message, "أهلاً! بوت فواصل كوميديا جاهز 🔥\nاستخدم /makevideo لإنشاء فيديو جديد تلقائياً.")

@bot.message_handler(commands=['channelid'])
def handle_channelid(message):
    bot.reply_to(message, f"هذا الـ chat.id الخاص بك:\n{message.chat.id}")

@bot.message_handler(commands=['makevideo'])
def handle_makevideo(message):
    user = message.from_user.username or message.from_user.first_name
    bot.reply_to(message, "⏳ جاري إنشاء الفاصل... انتظر ثوانٍ.")
    try:
        prompt = generate_prompt()
        logging.info(f"Prompt generated by {user}: {prompt}")
        video_path = request_geminigen_video(prompt)
        send_video_to_telegram_channel(video_path, caption=f"فاصل توليده AI — {prompt}")
        bot.reply_to(message, "✅ تم إنشاء الفيديو ونشره في القناة!")
        # مسح الملف المؤقت
        try:
            os.remove(video_path)
        except:
            pass
    except Exception as e:
        logging.exception("Error during makevideo")
        bot.reply_to(message, f"❌ حدث خطأ أثناء الإنشاء: {str(e)}")

# ------------- وظائف مساعدة للرفع إلى YouTube / TikTok / Instagram -------------
# ملاحظة: تحتاج إعداد OAuth و Tokens محددة؛ هذه توابع مكانية (stubs) تمهيدية.
def upload_to_youtube(file_path, title="AI Short", description="Generated by GeminiGen"):
    if not YOUTUBE_ACCESS_TOKEN:
        logging.warning("No YOUTUBE_ACCESS_TOKEN provided. Skipping YouTube upload.")
        return None
    # هنا تضع منطق الUpload باستخدام YouTube Data API (resumable upload)
    logging.info("YouTube upload: function not implemented, add your code.")
    return None

def upload_to_instagram(file_path, caption=""):
    if not INSTAGRAM_ACCESS_TOKEN:
        logging.warning("No INSTAGRAM_ACCESS_TOKEN provided. Skipping Instagram upload.")
        return None
    # استخدام Instagram Graph API يتطلب رفع المرحلة 1 ومرحلة 2، وتحتاج business account
    logging.info("Instagram upload: function not implemented, add your code.")
    return None

def upload_to_tiktok(file_path, caption=""):
    if not TIKTOK_ACCESS_TOKEN:
        logging.warning("No TIKTOK_ACCESS_TOKEN provided. Skipping TikTok upload.")
        return None
    logging.info("TikTok upload: function not implemented, add your code.")
    return None

# ------------- تشغيل Flask في Thread ثم تشغيل البوت (polling) -------------
if __name__ == "__main__":
    # تشغيل الويب سيرفر في Thread حتى يرى Render المنفذ مفتوحاً
    t = Thread(target=run_flask, daemon=True)
    t.start()

    logging.info("Starting Telegram polling...")
    # infinity_polling يسمح للبوت بالعمل باستمرار
    bot.infinity_polling(timeout=20, long_polling_timeout=60)
