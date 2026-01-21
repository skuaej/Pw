import os
import sys
from pyrogram import Client, filters
from aiohttp import web
import motor.motor_asyncio
import aiohttp_cors
import asyncio

# --- PRINT FUNCTION TO FORCE LOGS --- #
def log(text):
    print(text, flush=True)

# --- CONFIGURATION --- #
try:
    API_ID = int(os.environ.get("API_ID", 0))
    API_HASH = os.environ.get("API_HASH", "")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
    MONGO_URL = os.environ.get("MONGO_URL", "")
    PORT = int(os.environ.get("PORT", 8080))
except Exception as e:
    log(f"Config Error: {e}")

log(f"--- BOT CONFIGURATION ---")
log(f"Channel ID to Watch: {CHANNEL_ID}")
log(f"Port: {PORT}")
# ----------------------------- #

# --- DATABASE SETUP --- #
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = mongo_client["my_website_db"]
collection = db["files"]

# --- BOT SETUP --- #
app = Client("auto_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- HELPER: SAVE FILE TO DB --- #
async def save_to_db(message):
    media = None
    name = "Unknown"
    file_type = "unknown"
    
    # Identify Media
    if message.video:
        media = message.video
        name = message.video.file_name or message.caption or "Video"
        file_type = "video"
    elif message.document:
        media = message.document
        name = message.document.file_name
        file_type = "document"
    elif message.photo:
        media = message.photo
        name = message.caption or "Image"
        file_type = "image"
    elif message.audio:
        media = message.audio
        name = message.audio.file_name
        file_type = "audio"

    if media:
        try:
            exist = await collection.find_one({"msg_id": message.id})
            if not exist:
                file_data = {
                    "msg_id": message.id,
                    "name": name,
                    "type": file_type,
                    "size": media.file_size
                }
                await collection.insert_one(file_data)
                log(f"✅ Saved to DB: {name} (ID: {message.id})")
            else:
                log(f"⚠️ Already in DB: {name}")
        except Exception as e:
            log(f"❌ Database Error: {e}")

# --- BOT EVENTS --- #

@app.on_message(filters.command("start"))
async def start_msg(client, message):
    await message.reply_text("Bot is Running! Send files to the channel.")
    log("Start command received.")

# 1. Start hote hi check karega
async def check_connection():
    log("🔄 Checking Channel Connection...")
    try:
        chat = await app.get_chat(CHANNEL_ID)
        log(f"✅ Connected to Channel: {chat.title}")
    except Exception as e:
        log(f"❌ ERROR: Could not connect to Channel {CHANNEL_ID}")
        log(f"Reason: {e}")
        log("Make sure Bot is ADMIN in the channel!")

# 2. Jab bhi naya message aaye
@app.on_message(filters.chat(CHANNEL_ID) & filters.media)
async def new_post(client, message):
    log(f"📩 New Message Received! ID: {message.id}")
    await save_to_db(message)

# --- WEB SERVER ROUTES --- #
async def api_get_files(request):
    files = []
    cursor = collection.find().sort("msg_id", -1).limit(50)
    async for document in cursor:
        files.append({
            "id": document["msg_id"],
            "name": document["name"],
            "type": document["type"],
            "url": f"/stream/{document['msg_id']}"
        })
    return web.json_response(files)

async def stream_handler(request):
    try:
        msg_id = int(request.match_info['msg_id'])
        log(f"Streaming request for ID: {msg_id}")
        msg = await app.get_messages(CHANNEL_ID, msg_id)
        
        media = getattr(msg, msg.media.value) if msg.media else None
        if not media: return web.Response(status=404)

        resp = web.StreamResponse(
            status=200, 
            reason='OK', 
            headers={
                'Content-Type': getattr(media, 'mime_type', 'application/octet-stream'),
                'Content-Disposition': f'inline; filename="{getattr(media, "file_name", "file")}"',
                'Content-Length': str(media.file_size)
            }
        )
        await resp.prepare(request)
        async for chunk in app.stream_media(media):
            await resp.write(chunk)
        return resp
    except Exception as e:
        log(f"Stream Error: {e}")
        return web.Response(status=404)

async def health(r): return web.Response(text="Running")

# --- MAIN RUNNER --- #
if __name__ == "__main__":
    log("🚀 Starting Bot...")
    app.start()
    
    # Check Connection
    app.loop.create_task(check_connection())

    # Web Server
    server = web.Application()
    cors = aiohttp_cors.setup(server, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True, expose_headers="*", allow_headers="*",
        )
    })
    
    server.add_routes([
        web.get('/', health),
        web.get('/api/files', api_get_files),
        web.get('/stream/{msg_id}', stream_handler)
    ])
    
    for route in list(server.router.routes()):
        cors.add(route)

    log(f"🌍 Web Server running on port {PORT}")
    web.run_app(server, port=PORT)
