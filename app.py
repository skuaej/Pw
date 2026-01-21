import os
import requests
import asyncio
from flask import (
    Flask, request, render_template_string,
    redirect, Response, stream_with_context
)
from telegram import Update
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
BASE_URL = os.getenv("BASE_URL")

FILES_DB = []

app = Flask(__name__)
bot_app = Application.builder().token(BOT_TOKEN).build()

# 🔴 REQUIRED: initialize Telegram Application ONCE
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(bot_app.initialize())

HTML = """
<!doctype html>
<html>
<head>
<title>Telegram File Server</title>
<style>
body{font-family:Arial;background:#111;color:#fff;padding:20px}
.card{background:#222;padding:15px;margin:10px;border-radius:10px}
a{color:#0af;text-decoration:none}
</style>
</head>
<body>
<h2>📁 File Server</h2>
{% if files|length == 0 %}
<p>No files yet. Send files to the Telegram channel.</p>
{% endif %}
{% for f in files %}
<div class="card">
<b>{{f['name']}}</b><br>
Type: {{f['type']}} | Size: {{ (f.get('size',0) / 1024 / 1024)|round(2) }} MB<br>
<a href="/download/{{loop.index0}}">⬇ Download</a> |
<a href="/player/{{loop.index0}}">▶ Stream</a>
</div>
{% endfor %}
</body>
</html>
"""

TELEGRAM_FILE_BASE = f"https://api.telegram.org/file/bot{BOT_TOKEN}/"

# ---------------- HELPERS ----------------

def get_telegram_file_url(file_id):
    r = requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
        params={"file_id": file_id},
        timeout=30
    ).json()

    print("📥 getFile:", r)

    if not r.get("ok"):
        return None, None, None

    path = r["result"]["file_path"]
    size = r["result"].get("file_size")
    mime = r["result"].get("mime_type")

    return TELEGRAM_FILE_BASE + path, size, mime


# ---------------- WEB ROUTES ----------------

@app.route("/")
def home():
    return render_template_string(HTML, files=FILES_DB)


@app.route("/player/<int:i>")
def player(i):
    file = FILES_DB[i]

    if file["type"] != "video":
        return redirect(f"/download/{i}")

    return f"""
    <!doctype html>
    <html>
    <head>
        <title>{file['name']}</title>
    </head>
    <body style="background:#000;color:#fff;text-align:center">
        <h3>{file['name']}</h3>
        <video width="90%" controls autoplay>
            <source src="/stream/{i}" type="video/mp4">
            Your browser does not support video playback.
        </video>
    </body>
    </html>
    """


@app.route("/download/<int:i>")
def download(i):
    file_id = FILES_DB[i]["file_id"]
    file_url, size, mime = get_telegram_file_url(file_id)

    if not file_url:
        return "❌ Telegram could not provide this file.", 502

    r = requests.get(file_url, stream=True, timeout=60)

    def generate():
        for chunk in r.iter_content(chunk_size=1024 * 512):
            if chunk:
                yield chunk

    headers = {
        "Content-Disposition": f'attachment; filename="{FILES_DB[i]["name"]}"',
        "Content-Type": mime or "application/octet-stream",
    }

    if size:
        headers["Content-Length"] = str(size)

    return Response(stream_with_context(generate()), headers=headers)


@app.route("/stream/<int:i>")
def stream(i):
    file_id = FILES_DB[i]["file_id"]
    file_url, size, mime = get_telegram_file_url(file_id)

    if not file_url:
        return "❌ Telegram could not provide this file.", 502

    range_header = request.headers.get("Range", None)
    headers = {}

    if range_header:
        headers["Range"] = range_header
        print("📡 Range request:", range_header)

    r = requests.get(file_url, headers=headers, stream=True, timeout=60)

    def generate():
        for chunk in r.iter_content(chunk_size=1024 * 256):
            if chunk:
                yield chunk

    response_headers = {
        "Content-Type": r.headers.get("Content-Type", mime or "video/mp4"),
        "Accept-Ranges": "bytes",
    }

    if "Content-Range" in r.headers:
        response_headers["Content-Range"] = r.headers["Content-Range"]

    if "Content-Length" in r.headers:
        response_headers["Content-Length"] = r.headers["Content-Length"]

    return Response(
        stream_with_context(generate()),
        status=r.status_code,
        headers=response_headers,
    )


@app.route("/endpoint", methods=["POST"])
def telegram_webhook():
    data = request.get_json(force=True, silent=True)
    print("📩 RAW UPDATE:", data)

    if not data:
        return "NO DATA", 400

    update = Update.de_json(data, bot_app.bot)
    loop.run_until_complete(bot_app.process_update(update))

    return "OK"


@app.route("/setwebhook")
def set_webhook():
    r = requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
        params={"url": f"{BASE_URL}/endpoint"}
    ).json()

    print("🔗 setWebhook:", r)
    return r


# ---------------- BOT HANDLERS ----------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("👋 /start from:", update.effective_user.id)

    await update.message.reply_text(
        "✅ I am online!\n\n"
        "Send files to the channel and view them here:\n"
        f"{BASE_URL}"
    )


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("🏓 /ping from:", update.effective_user.id)
    await update.message.reply_text("🏓 Pong! Bot is alive.")


async def handle_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post

    if not msg:
        print("❌ Not a channel post")
        return

    print("📦 CHANNEL POST RECEIVED")

    file_data = None

    if msg.video:
        f = msg.video
        file_data = {
            "file_id": f.file_id,
            "name": f.file_name or "video.mp4",
            "type": "video",
            "size": f.file_size
        }

    elif msg.document:
        f = msg.document
        file_data = {
            "file_id": f.file_id,
            "name": f.file_name or "file",
            "type": "document",
            "size": f.file_size
        }

    elif msg.audio:
        f = msg.audio
        file_data = {
            "file_id": f.file_id,
            "name": f.file_name or "audio.mp3",
            "type": "audio",
            "size": f.file_size
        }

    elif msg.photo:
        f = msg.photo[-1]
        file_data = {
            "file_id": f.file_id,
            "name": "image.jpg",
            "type": "image",
            "size": f.file_size
        }

    if file_data:
        FILES_DB.append(file_data)
        print("✅ FILE STORED:", file_data)
        print("📊 TOTAL FILES:", len(FILES_DB))
    else:
        print("ℹ Channel post but not a supported file")


# Register handlers
bot_app.add_handler(CommandHandler("start", start_command))
bot_app.add_handler(CommandHandler("ping", ping_command))

bot_app.add_handler(
    MessageHandler(
        filters.VIDEO | filters.Document.ALL | filters.AUDIO | filters.PHOTO,
        handle_files
    )
)

# ---------------- START ----------------

if __name__ == "__main__":
    print("🚀 Bot starting...")
    print("🌐 BASE_URL:", BASE_URL)
    print("📢 CHANNEL_ID:", CHANNEL_ID)

    app.run(host="0.0.0.0", port=8000)
