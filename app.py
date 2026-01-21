import os
from flask import Flask, request, jsonify
import requests

# ========= CONFIG =========
BOT_TOKEN = "YOUR_BOT_TOKEN"
BOT_SECRET = "BOT_SECRET"
BOT_WEBHOOK = "/endpoint"

BASE_URL = "https://balanced-tahr-uhhy5-1600dc3b.koyeb.app"  # apna koyeb URL
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = Flask(__name__)


# ---------- HEALTH CHECK ----------
@app.route("/", methods=["GET"])
def home():
    return "Telegram Webhook Bot is Running!", 200


# ---------- STREAM ROUTE ----------
@app.route("/stream/<file_id>", methods=["GET"])
def stream_file(file_id):
    r = requests.get(
        f"{TELEGRAM_API}/getFile",
        params={"file_id": file_id},
        timeout=10
    )
    data = r.json()

    if not data.get("ok"):
        return "Invalid file_id", 404

    file_path = data["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

    return jsonify({
        "ok": True,
        "file_url": file_url
    })


# ---------- WEBHOOK ----------
@app.route(BOT_WEBHOOK, methods=["POST"])
def webhook():
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != BOT_SECRET:
        return "Unauthorized", 403

    update = request.get_json(force=True)

    if "message" in update:
        handle_message(update["message"])

    return "OK", 200


# ---------- MESSAGE HANDLER ----------
def handle_message(message):
    chat_id = message["chat"]["id"]

    # ---- /start ----
    if "text" in message and message["text"].strip() == "/start":
        send_message(
            chat_id,
            "👋 Welcome!\n\n"
            "Send me:\n"
            "• Any file\n"
            "• Any video\n\n"
            "Main tumhe:\n"
            "• stream link\n"
            "• download link\n"
            "• thumbnail link (video)\n\n"
            "de dunga 😎"
        )
        return

    # ---- DOCUMENT ----
    if "document" in message:
        doc = message["document"]
        file_id = doc["file_id"]
        name = doc.get("file_name", "file")

        stream_link = f"{BASE_URL}/stream/{file_id}"

        send_message(
            chat_id,
            f"📁 File Received!\n\n"
            f"Name: {name}\n\n"
            f"▶️ Stream / Download:\n{stream_link}"
        )
        return

    # ---- VIDEO ----
    if "video" in message:
        vid = message["video"]
        file_id = vid["file_id"]

        stream_link = f"{BASE_URL}/stream/{file_id}"

        thumb_text = "❌ No thumbnail"
        if "thumbnail" in vid:
            thumb_id = vid["thumbnail"]["file_id"]
            thumb_link = f"{BASE_URL}/stream/{thumb_id}"
            thumb_text = f"🖼 Thumbnail Link:\n{thumb_link}"

        send_message(
            chat_id,
            f"🎬 Video Received!\n\n"
            f"▶️ Stream / Download:\n{stream_link}\n\n"
            f"{thumb_text}"
        )
        return

    send_message(chat_id, "❌ Sirf file ya video bhejo.")


# ---------- SEND MESSAGE ----------
def send_message(chat_id, text):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Send error:", e)


# ---------- MAIN ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
