import os
from flask import Flask, request
import requests

# ========= CONFIG =========
BOT_TOKEN = "8234149040:AAGsdw8QZbtKcUgylM2mn8aNW07xc7YYMpk"
BOT_SECRET = "Byjjjy56uujjjjnj666"
BOT_WEBHOOK = "/endpoint"

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = Flask(__name__)


# -------- Home --------
@app.route("/", methods=["GET"])
def home():
    return "✅ Telegram Webhook Bot is Running!", 200


# -------- Webhook --------
@app.route(BOT_WEBHOOK, methods=["POST"])
def webhook():
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != BOT_SECRET:
        return "Unauthorized", 403

    update = request.get_json(force=True)

    if "message" in update:
        handle_message(update["message"])

    return "OK", 200


# -------- Message Handler --------
def handle_message(message):
    chat_id = message["chat"]["id"]

    # ---- TEXT ----
    if "text" in message:
        text = message["text"].strip()

        if text == "/start":
            send_message(
                chat_id,
                "👋 Welcome!\n\n"
                "Send me:\n"
                "• Text\n"
                "• Files\n"
                "• Videos\n\n"
                "Main file/video ka file_id + thumbnail info de dunga 😎"
            )
            return

        send_message(chat_id, f"📩 You said:\n{text}")
        return

    # ---- DOCUMENT (FILES) ----
    if "document" in message:
        doc = message["document"]
        file_id = doc["file_id"]
        file_name = doc.get("file_name", "unknown")
        file_size = doc.get("file_size", 0)

        reply = (
            "📁 File Received!\n\n"
            f"Name: {file_name}\n"
            f"Size: {file_size} bytes\n"
            f"File ID:\n{file_id}"
        )

        send_message(chat_id, reply)
        return

    # ---- VIDEO ----
    if "video" in message:
        vid = message["video"]
        file_id = vid["file_id"]
        file_size = vid.get("file_size", 0)
        duration = vid.get("duration", 0)
        width = vid.get("width", 0)
        height = vid.get("height", 0)

        thumb_info = "❌ No thumbnail"
        if "thumbnail" in vid:
            thumb = vid["thumbnail"]
            thumb_file_id = thumb["file_id"]
            thumb_w = thumb.get("width", 0)
            thumb_h = thumb.get("height", 0)

            thumb_info = (
                "🖼 Thumbnail Info:\n"
                f"Thumb File ID:\n{thumb_file_id}\n"
                f"Resolution: {thumb_w}x{thumb_h}"
            )

        reply = (
            "🎬 Video Received!\n\n"
            f"Duration: {duration} sec\n"
            f"Resolution: {width}x{height}\n"
            f"Size: {file_size} bytes\n\n"
            f"Video File ID:\n{file_id}\n\n"
            f"{thumb_info}"
        )

        send_message(chat_id, reply)
        return

    # ---- PHOTO ----
    if "photo" in message:
        photos = message["photo"]
        best = photos[-1]   # highest resolution
        file_id = best["file_id"]
        width = best.get("width", 0)
        height = best.get("height", 0)
        file_size = best.get("file_size", 0)

        reply = (
            "🖼 Photo Received!\n\n"
            f"Resolution: {width}x{height}\n"
            f"Size: {file_size} bytes\n\n"
            f"File ID:\n{file_id}"
        )

        send_message(chat_id, reply)
        return

    # ---- OTHER ----
    send_message(chat_id, "❌ Unsupported message type.")


# -------- Send Message --------
def send_message(chat_id, text):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Send error:", e)


# -------- Main --------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
