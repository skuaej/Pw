import os
import asyncio
import requests
from flask import (
    Flask, request, render_template_string,
    redirect, Response, stream_with_context
)
from telegram import Update
from telegram.ext import (
    Application, ContextTypes,
    MessageHandler, CommandHandler, filters
)
from telethon import TelegramClient

# ---------------- CONFIG ----------------

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
BASE_URL = os.getenv("BASE_URL")

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("SESSION_NAME", "telethon")

FILES_DB = []  # in-memory (replace with MongoDB later)

# ---------------- INIT ----------------

app = Flask(__name__)

bot_app = Application.builder().token(BOT_TOKEN).build()

tg_loop = asyncio.new_event_loop()
asyncio.set_event_loop(tg_loop)

tg_client = TelegramClient(SESSION_NAME, API_ID, API_HASH, loop=tg_loop)
tg_loop.run_until_complete(tg_client.start())

tg_loop.run_until_complete(bot_app.initialize())

# ---------------- HTML ----------------

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
Type: {{f['type']}} |
Size: {{ (f['size'] / 1024 / 1024)|round(2) }} MB<br>
<a href="/download/{{loop.index0}}">⬇ Download</a> |
<a href="/player/{{loop.index0}}">▶ Stream</a>
</div>
{% endfor %}
</body>
</html>
"""

# ---------------- HELPERS ----------------

async def iter_telethon_download(chat_id, message_id, offset=0, limit=None):
    msg = await tg_client.get_messages(chat_id, ids=message_id)

    async for chunk in tg_client.iter_download(
        msg.media,
        offset=offset,
        limit=limit,
        chunk_size=512 * 1024
    ):
        yield chunk


def run_async(gen_func):
    loop = tg_loop
    agen = gen_func

    async def iterate():
        async for c in agen:
            yield c

    it = iterate()

    def generator():
        while True:
            try:
                chunk = loop.run_until_complete(it.__anext__())
                yield chunk
            except StopAsyncIteration:
                break

    return generator()

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
    <head><title>{file['name']}</title></head>
    <body style="background:#000;color:#fff;text-align:center">
        <h3>{file['name']}</h3>
        <video width="90%" controls autoplay>
            <source src="/stream/{i}" type="video/mp4">
        </video>
    </body>
    </html>
    """


@app.route("/download/<int:i>")
def download(i):
    file = FILES_DB[i]

    gen = run_async(
        iter_telethon_download(file["chat_id"], file["message_id"])
    )

    headers = {
        "Content-Disposition": f'attachment; filename="{file["name"]}"',
        "Content-Type": "application/octet-stream",
        "Content-Length": str(file["size"]),
    }

    return Response(stream_with_context(gen), headers=headers)


@app.route("/stream/<int:i>")
def stream(i):
    file = FILES_DB[i]

    range_header = request.headers.get("Range", None)
    start = 0
    end = file["size"] - 1

    if range_header:
        _, rng = range_header.split("=")
        start, end = rng.split("-")
        start = int(start)
        end = int(end) if end else file["size"] - 1

    length = end - start + 1

    gen = run_async(
        iter_telethon_download(
            file["chat_id"],
            file["message_id"],
            offset=start,
            limit=length
        )
    )

    headers = {
        "Content-Type": "video/mp4",
        "Accept-Ranges": "bytes",
        "Content-Range": f"bytes {start}-{end}/{file['size']}",
        "Content-Length": str(length),
    }

    return Response(
        stream_with_context(gen),
        status=206 if range_header else 200,
        headers=headers
    )


@app.route("/endpoint", methods=["POST"])
def telegram_webhook():
    data = request.get_json(force=True, silent=True)
    print("📩 RAW UPDATE:", data)

    if not data:
        return "NO DATA", 400

    update = Update.de_json(data, bot_app.bot)
    tg_loop.run_until_complete(bot_app.process_update(update))

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
    await update.message.reply_text(
        "✅ I am online!\n\n"
        "Send files to the channel and view them here:\n"
        f"{BASE_URL}"
    )


async def handle_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post
    if not msg:
        return

    print("📦 CHANNEL POST RECEIVED")

    file_data = None

    if msg.video:
        f = msg.video
        file_data = {
            "chat_id": msg.chat.id,
            "message_id": msg.message_id,
            "file_id": f.file_id,
            "name": f.file_name or "video.mp4",
            "type": "video",
            "size": f.file_size
        }

    elif msg.document:
        f = msg.document
        file_data = {
            "chat_id": msg.chat.id,
            "message_id": msg.message_id,
            "file_id": f.file_id,
            "name": f.file_name or "file",
            "type": "document",
            "size": f.file_size
        }

    elif msg.audio:
        f = msg.audio
        file_data = {
            "chat_id": msg.chat.id,
            "message_id": msg.message_id,
            "file_id": f.file_id,
            "name": f.file_name or "audio.mp3",
            "type": "audio",
            "size": f.file_size
        }

    if file_data:
        FILES_DB.append(file_data)
        print("✅ FILE STORED:", file_data)
        print("📊 TOTAL FILES:", len(FILES_DB))


bot_app.add_handler(CommandHandler("start", start_command))

bot_app.add_handler(
    MessageHandler(
        filters.VIDEO | filters.Document.ALL | filters.AUDIO,
        handle_files
    )
)

# ---------------- START ----------------

if __name__ == "__main__":
    print("🚀 Server starting...")
    print("🌐 BASE_URL:", BASE_URL)
    print("📢 CHANNEL_ID:", CHANNEL_ID)

    app.run(host="0.0.0.0", port=8000)
