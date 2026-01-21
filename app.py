import os
from flask import Flask, request, jsonify
import requests

# ========= CONFIG =========
BOT_TOKEN = "YOUR_BOT_TOKEN"
BOT_SECRET = "BOT_SECRET"
BOT_WEBHOOK = "/endpoint"

BASE_URL = "https://balanced-tahr-uhhy5-1600dc3b.koyeb.app"   # apna koyeb URL
CHANNEL_ID = -1002432952660  # 👈 apna channel id daal

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = Flask(__name__)


# ---------- HEALTH ----------
@app.route("/", methods=["GET"])
def home():
    return "Telegram Stream Bot Running!", 200


# ---------- STREAM ----------
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

    return jsonify({"ok": True, "file_url": file_url})


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


# ---------- HANDLER ----------
def handle_message(message):
    chat_id = message["chat"]["id"]

    # ---- /start ----
    if "text" in message and message["text"].strip() == "/start":
        send_message(
            chat_id,
            "👋 Welcome!\n\n"
            "Send me any file or video.\n\n"
            "Main:\n"
            "• channel me upload karunga\n"
            "• stream/download link dunga\n"
            "• thumbnail link dunga (video)\n"
        )
        return

    # ---- DOCUMENT ----
    if "document" in message:
        doc = message["document"]
        file_id = doc["file_id"]
        name = doc.get("file_name", "file")

        print(f"[FILE] name={name} file_id={file_id}")

        # forward to channel
        forward_to_channel(chat_id, message["message_id"])

        stream_link = f"{BASE_URL}/stream/{file_id}"

        send_message(
            chat_id,
            f"📁 File Received & Uploaded to Channel!\n\n"
            f"Name: {name}\n\n"
            f"▶️ Stream / Download:\n{stream_link}"
        )
        return

    # ---- VIDEO ----
    if "video" in message:
        vid = message["video"]
        file_id = vid["file_id"]

        print(f"[VIDEO] file_id={file_id}")

        forward_to_channel(chat_id, message["message_id"])

        stream_link = f"{BASE_URL}/stream/{file_id}"

        thumb_text = "❌ No thumbnail"
        if "thumbnail" in vid:
            thumb_id = vid["thumbnail"]["file_id"]
            thumb_link = f"{BASE_URL}/stream/{thumb_id}"
            thumb_text = f"🖼 Thumbnail Link:\n{thumb_link}"

            print(f"[THUMB] thumb_file_id={thumb_id}")

        send_message(
            chat_id,
            f"🎬 Video Received & Uploaded to Channel!\n\n"
            f"▶️ Stream / Download:\n{stream_link}\n\n"
            f"{thumb_text}"
        )
        return

    send_message(chat_id, "❌ Sirf file ya video bhejo.")


# ---------- HELPERS ----------
def send_message(chat_id, text):
    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=10
    )


def forward_to_channel(from_chat_id, message_id):
    requests.post(
        f"{TELEGRAM_API}/forwardMessage",
        json={
            "chat_id": CHANNEL_ID,
            "from_chat_id": from_chat_id,
            "message_id": message_id
        },
        timeout=10
    )


# ---------- MAIN ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
