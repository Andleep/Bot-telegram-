# bot.py
import os
import time
import random
import requests
import telebot
from flask import Flask, request, abort
from threading import Thread

# -------------------------
# CONFIG - from environment
# -------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")            # BotFather token
CHANNEL_ID = os.getenv("CHANNEL_ID")          # -100... or @channelname
GEMINI_KEY = os.getenv("GEMINI_KEY")          # GeminiGen API key
WEBHOOK_URL = os.getenv("WEBHOOK_URL")        # e.g. https://your-render-url.com/<BOT_TOKEN>
PORT = int(os.getenv("PORT", 10000))

# Basic check
if not all([BOT_TOKEN, CHANNEL_ID, GEMINI_KEY, WEBHOOK_URL]):
    print("❌ Missing env vars. Set BOT_TOKEN, CHANNEL_ID, GEMINI_KEY, WEBHOOK_URL")
    raise SystemExit(1)

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# -------------------------
# Sora endpoints / config
# -------------------------
SORA_ENDPOINT = "https://api.geminigen.ai/uapi/v1/video-gen/sora"
SORA_STATUS_BY_UUID = "https://api.geminigen.ai/uapi/v1/video-gen/sora/{uuid}"
HEADERS = {"x-api-key": GEMINI_KEY}

# -------------------------
# Prompt generator (AI-like simple generator)
# Produces English prompt describing a funny Arabic scene
# -------------------------
GULF_TEMPLATES = [
    "A short 10-second comedic Gulf skit with lively music and Arabic dialogue, close-up reactions, slapstick humor",
    "A comedic little scene in a Gulf cafe: a waiter spills tea but everyone laughs, Arabic dialogue, 10s",
    "A playful 10-second Gulf street moment: people dancing and playful greetings, comedic timing, Arabic speech"
]
EGYPT_TEMPLATES = [
    "A 10-second Egyptian comedic sketch with dramatic gestures and Arabic dialogue, comedic timing",
    "A short 10-second street comedy in Egypt: a vendor surprises customers, funny reactions, Arabic speech",
    "A funny Egyptian family moment: sister teases brother, comedic expressions, Arabic audio, 10s"
]
SYRIA_TEMPLATES = [
    "A short 10-second Syrian joke scene, playful banter and comedic reactions, Arabic dialogue",
    "A 10-second Syrian street comedy: someone trips on a rug but ends charmingly, Arabic speech, funny faces",
    "A quick Syrian comedic skit, neighbors laugh at a silly misunderstanding, Arabic audio, 10s"
]

def generate_english_prompt():
    # Choose region weight: Gulf 40%, Egypt 35%, Syria 25% (you can adjust)
    r = random.random()
    if r < 0.40:
        template = random.choice(GULF_TEMPLATES)
    elif r < 0.75:
        template = random.choice(EGYPT_TEMPLATES)
    else:
        template = random.choice(SYRIA_TEMPLATES)
    # Add short visual/camera hints to improve Sora output
    camera_clues = [
        "Use dynamic camera: slight pan and close-up shots",
        "Use bright daytime lighting and playful music",
        "Keep camera steady with quick cuts and expressive faces"
    ]
    prompt_en = f"{template}. {random.choice(camera_clues)}. Make dialogue in Arabic."
    return prompt_en

# -------------------------
# Create video (Sora) & poll
# - model: sora-2 (supports 10s)
# - resolution: small (720p)
# - duration: 10
# - aspect_ratio: landscape (16:9)
# -------------------------
def create_video_sora(prompt_en, timeout=600, poll_interval=4):
    data = {
        "prompt": prompt_en,
        "model": "sora-2",
        "resolution": "small",
        "duration": "10",
        "aspect_ratio": "landscape"
    }
    try:
        print("→ Sending Sora request:", {k: data[k] for k in data if k != "prompt"} )
        # use multipart/form-data (requests will encode automatically)
        resp = requests.post(SORA_ENDPOINT, headers=HEADERS, data=data, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        print("❌ Sora request failed:", e)
        try:
            print("response:", resp.status_code, resp.text)
        except:
            pass
        return None

    try:
        res_json = resp.json()
    except Exception as e:
        print("❌ Failed to decode Sora JSON:", e, resp.text)
        return None

    print("Sora initial response:", res_json)

    # If direct URL returned:
    for key in ("video_url", "url", "download_url"):
        if res_json.get(key):
            print("✅ Direct video URL received:", res_json.get(key))
            return res_json.get(key)

    # Otherwise get uuid/job id
    uuid = res_json.get("uuid") or res_json.get("id") or res_json.get("job_id")
    if not uuid:
        print("❌ No uuid/job id or video_url in Sora response; full response:", res_json)
        return None

    print("→ Job created, uuid/job_id:", uuid, " — start polling...")

    start = time.time()
    while time.time() - start < timeout:
        # try specific Sora status endpoint
        try:
            st_resp = requests.get(SORA_STATUS_BY_UUID.format(uuid=uuid), headers=HEADERS, timeout=30)
            if st_resp.status_code == 200:
                st_json = st_resp.json()
                print("Status response:", st_json)
                # per docs: status == 2 => completed
                if st_json.get("status") == 2:
                    # try common keys
                    for key in ("video_url", "url", "download_url"):
                        if st_json.get(key):
                            print("✅ Video ready (status endpoint):", st_json.get(key))
                            return st_json.get(key)
                    # sometimes media list
                    media = st_json.get("media") or st_json.get("files")
                    if media and isinstance(media, list):
                        for m in media:
                            if isinstance(m, dict) and (m.get("url") or m.get("download_url")):
                                print("✅ Video ready inside media list:", m)
                                return m.get("url") or m.get("download_url")
                # if status indicates failed
                if st_json.get("status") == 3:
                    print("❌ Generation failed:", st_json.get("error_message") or st_json)
                    return None
        except Exception as e:
            # ignore and continue polling
            # print("status check failed:", e)
            pass

        # fallback: try generic status endpoint by job_id
        try:
            st2 = requests.get("https://api.geminigen.ai/uapi/v1/status", headers=HEADERS, params={"job_id": uuid}, timeout=30)
            if st2.status_code == 200:
                j = st2.json()
                print("Generic status response:", j)
                if j.get("status") == 2 or j.get("status_desc", "").lower() == "completed":
                    for key in ("video_url", "url", "download_url"):
                        if j.get(key):
                            return j.get(key)
        except Exception:
            pass

        time.sleep(poll_interval)

    print("❌ Timeout waiting for Sora job to finish (uuid=%s)" % uuid)
    return None

# -------------------------
# Send video to Telegram channel
# -------------------------
def send_video_to_channel(video_url, caption=None):
    if not video_url:
        print("❌ No video_url to send")
        return False
    try:
        # first send a message with caption then send video by URL
        if caption:
            bot.send_message(CHANNEL_ID, caption)
        bot.send_video(CHANNEL_ID, video_url)
        print("✅ Sent video to channel:", video_url)
        return True
    except Exception as e:
        print("❌ Telegram send failed:", e)
        # fallback: download then upload
        try:
            dl = requests.get(video_url, stream=True, timeout=120)
            dl.raise_for_status()
            files = {"video": dl.raw}
            resp = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo",
                                 data={"chat_id": CHANNEL_ID, "caption": caption or ""}, files=files, timeout=180)
            print("Fallback upload resp:", resp.status_code, resp.text[:300])
            return resp.status_code == 200
        except Exception as e2:
            print("❌ Fallback upload failed:", e2)
            return False

# -------------------------
# Worker: generate every 8 minutes
# -------------------------
def worker_loop():
    while True:
        prompt_en = generate_english_prompt()
        print("⏳ Generating prompt (EN):", prompt_en)
        video_url = create_video_sora(prompt_en, timeout=900, poll_interval=5)  # timeout longer for Sora
        if video_url:
            caption = f"فاصل مضحك — {time.strftime('%Y-%m-%d %H:%M:%S')}"
            send_video_to_channel(video_url, caption=caption)
        else:
            print("❌ Could not generate video for prompt:", prompt_en)
        print("⏰ Waiting 8 minutes until next generation...")
        time.sleep(8 * 60)  # 8 minutes

# -------------------------
# Webhook endpoint for Telegram
# (route uses BOT_TOKEN to make it unique)
# -------------------------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    if request.headers.get("content-type", "").startswith("application/json"):
        json_str = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return "", 200
    return abort(403)

@app.route("/", methods=["GET"])
def home():
    return "Bot running", 200

# -------------------------
# Bot command handlers
# -------------------------
@bot.message_handler(commands=["start"])
def cmd_start(m):
    bot.reply_to(m, "مرحبًا! البوت يعمل وسيُنشيء فيديو مضحك كل 8 دقائق 🎬")

@bot.message_handler(commands=["makevideo"])
def cmd_makevideo(m):
    bot.reply_to(m, "⏳ سيتم إنشاء فيديو الآن (يدوياً)...")
    prompt_en = generate_english_prompt()
    video_url = create_video_sora(prompt_en, timeout=900, poll_interval=5)
    if video_url:
        send_video_to_channel(video_url, caption=f"فاصل مولد يدوياً — {prompt_en}")
        bot.reply_to(m, "✅ تم الإنشاء والإرسال")
    else:
        bot.reply_to(m, "❌ فشل إنشاء الفيديو. راجع السجلات.")

# -------------------------
# Start: set webhook + start worker thread + run Flask
# -------------------------
def start_all():
    try:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        print("✅ Webhook set to:", WEBHOOK_URL)
    except Exception as e:
        print("❌ Webhook set error:", e)

    t = Thread(target=worker_loop, daemon=True)
    t.start()
    print("🟢 Worker thread started (every 8 minutes)")

if __name__ == "__main__":
    start_all()
    app.run(host="0.0.0.0", port=PORT)
