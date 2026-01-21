import os
import requests
from flask import Flask, render_template_string, redirect
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import threading

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME")  # without @
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))  # -100xxxx

FILES_DB = []

app = Flask(__name__)

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

@app.route("/")
def home():
    return render_template_string(HTML, files=FILES_DB)

@app.route("/download/<int:i>")
def download(i):
    file_id = FILES_DB[i]["file_id"]
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
    r = requests.get(url).json()
    path = r["result"]["file_path"]
    return redirect(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}")

@app.route("/stream/<int:i>")
def stream(i):
    file_id = FILES_DB[i]["file_id"]
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
    r = requests.get(url).json()
    path = r["result"]["file_path"]
    return redirect(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}")

async def handle_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post

    if msg.video:
        f = msg.video
        FILES_DB.append({"file_id": f.file_id, "name": "video.mp4", "type": "video"})
    elif msg.document:
        f = msg.document
        FILES_DB.append({"file_id": f.file_id, "name": f.file_name, "type": "document"})
    elif msg.audio:
        f = msg.audio
        FILES_DB.append({"file_id": f.file_id, "name": f.file_name, "type": "audio"})
    elif msg.photo:
        f = msg.photo[-1]
        FILES_DB.append({"file_id": f.file_id, "name": "image.jpg", "type": "image"})

    await context.bot.send_message(
        chat_id=CHANNEL_ID,
        text="✅ File added to web server!"
    )

def run_bot():
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(MessageHandler(filters.ALL, handle_files))
    app_bot.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=8000)
