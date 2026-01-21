import os
import requests
import asyncio
from flask import Flask, request, render_template_string, redirect
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

# 🔴 CRITICAL: initialize the Telegram application ONCE
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
Type: {{f['type']}}<br>
<a href="/download/{{loop.index0}}">⬇ Download</a> |
<a href="/stream/{{loop.index0}}">▶ Stream</a>
</div>
{% endfor %}
</body>
</html>
"""

# ---------------- WEB ROUTES ----------------

@app.route("/")
def home():
    return render_template_string(HTML, files=FILES_DB)

@app.route("/download/<int:i>")
def download(i):
    file_id = FILES_DB[i]["file_id"]
    r = requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
        params={"file_id": file_id},
        timeout=15
    ).json()
    path = r["result"]["file_path"]
    return redirect(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}")

@app.route("/stream/<int:i>")
def stream(i):
    return download(i)

@app.route("/endpoint", methods=["POST"])
def telegram_webhook():
    data = request.get_json(force=True, silent=True)
    print("📩 RAW UPDATE:", data)

    if not data:
        return "NO DATA", 400

    update = Update.de_json(data, bot_app.bot)

    # reuse same event loop
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
        file_data = {"file_id": f.file_id, "name": "video.mp4", "type": "video"}

    elif msg.document:
        f = msg.document
        file_data = {"file_id": f.file_id, "name": f.file_name or "file", "type": "document"}

    elif msg.audio:
        f = msg.audio
        file_data = {"file_id": f.file_id, "name": f.file_name or "audio.mp3", "type": "audio"}

    elif msg.photo:
        f = msg.photo[-1]
        file_data = {"file_id": f.file_id, "name": "image.jpg", "type": "image"}

    if file_data:
        FILES_DB.append(file_data)
        print("✅ FILE STORED:", file_data)
        print("📊 TOTAL FILES:", len(FILES_DB))
    else:
        print("ℹ Channel post but not a file")

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
