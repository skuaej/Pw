from flask import Flask, request, Response
import requests
import sqlite3
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
print("BOT_TOKEN loaded:", bool(BOT_TOKEN))

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN env var not set")

app = Flask(__name__)

# ---------- Database Setup ----------
conn = sqlite3.connect("files.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT,
    file_name TEXT,
    caption TEXT,
    thumb_id TEXT
)
""")
conn.commit()

# ---------- Webhook Receiver (CRASH-PROOF) ----------
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("----- NEW UPDATE -----")
        print(data)

        msg = None
        if isinstance(data, dict):
            if "channel_post" in data:
                msg = data["channel_post"]
            elif "message" in data:
                msg = data["message"]

        if not msg:
            return "ok"

        # ---------- /start ----------
        if msg.get("text") == "/start":
            chat_id = msg["chat"]["id"]
            r = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data={
                    "chat_id": chat_id,
                    "text": "✅ Bot is running on Koyeb!\nSend any file and it will appear on the web page."
                },
                timeout=10
            )
            print("sendMessage response:", r.text)
            return "ok"

        file_id = None
        file_name = None
        thumb_id = None

        doc = msg.get("document")
        vid = msg.get("video")
        photos = msg.get("photo")
        aud = msg.get("audio")

        if doc:
            file_id = doc.get("file_id")
            file_name = doc.get("file_name", "file")

        elif vid:
            file_id = vid.get("file_id")
            file_name = vid.get("file_name", "video.mp4")
            thumb = vid.get("thumbnail")
            if thumb:
                thumb_id = thumb.get("file_id")

        elif photos:
            file_id = photos[-1].get("file_id")
            file_name = "image.jpg"
            thumb_id = file_id

        elif aud:
            file_id = aud.get("file_id")
            file_name = aud.get("file_name", "audio.mp3")

        caption = msg.get("caption", "")

        if file_id and file_name:
            cur.execute(
                "INSERT INTO files (file_id, file_name, caption, thumb_id) VALUES (?, ?, ?, ?)",
                (file_id, file_name, caption, thumb_id)
            )
            conn.commit()
            print("Saved:", file_name)

        return "ok"

    except Exception as e:
        # 🔥 Prevents Telegram 500 + logs real error
        print("❌ WEBHOOK CRASH:", repr(e))
        return "ok"

# ---------- Home Page ----------
@app.route("/")
def index():
    cur.execute("SELECT id, file_id, file_name, caption, thumb_id FROM files ORDER BY id DESC")
    rows = cur.fetchall()

    html = """
    <html>
    <head>
        <title>Telegram Files</title>
        <style>
            body { font-family: Arial; background:#111; color:#eee; padding:20px; }
            a { color:#4ea3ff; text-decoration:none; }
            .file { margin-bottom:15px; padding:10px; background:#1c1c1c; border-radius:8px; }
            img { max-width:220px; border-radius:8px; display:block; margin-bottom:8px; }
        </style>
    </head>
    <body>
        <h2>📂 Telegram Files</h2>
    """

    for f in rows:
        thumb_html = ""
        if f[4]:
            thumb_html = f"<img src='/thumb/{f[4]}'>"

        html += f"""
        <div class='file'>
            {thumb_html}
            <b>{f[2]}</b><br>
            {f[3]}<br>
            <a href='/stream/{f[1]}'>Download / Watch</a>
        </div>
        """

    html += "</body></html>"
    return html

# ---------- Thumbnail Proxy ----------
@app.route("/thumb/<file_id>")
def thumb(file_id):
    r = requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
    ).json()

    if not r.get("ok"):
        return ""

    path = r["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}"

    resp = requests.get(file_url, stream=True)

    return Response(
        resp.iter_content(chunk_size=8192),
        content_type=resp.headers.get("Content-Type", "image/jpeg")
    )

# ---------- File Stream (Correct Filename) ----------
@app.route("/stream/<file_id>")
def stream(file_id):
    cur.execute("SELECT file_name FROM files WHERE file_id = ?", (file_id,))
    row = cur.fetchone()
    filename = row[0] if row else "file"

    r = requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
    ).json()

    if not r.get("ok"):
        return "File not found"

    path = r["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}"

    resp = requests.get(file_url, stream=True)

    return Response(
        resp.iter_content(chunk_size=8192),
        content_type=resp.headers.get("Content-Type", "application/octet-stream"),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )

# ---------- Health Check ----------
@app.route("/health")
def health():
    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
