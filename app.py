import os
import asyncio
from pyrogram import Client, filters
from aiohttp import web
import motor.motor_asyncio
import aiohttp_cors

# --- LOGGING FUNCTION ---
def log(text):
    print(f"[BOT_LOG] {text}", flush=True)

# --- CONFIGURATION ---
try:
    API_ID = int(os.environ.get("API_ID", 0))
    API_HASH = os.environ.get("API_HASH", "")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
    MONGO_URL = os.environ.get("MONGO_URL", "")
    PORT = int(os.environ.get("PORT", 8000))
except Exception as e:
    log(f"Config Error: {e}")

# --- DATABASE SETUP ---
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = mongo_client["Cluster0g"]
collection = db["files"]

# --- BOT CLIENT ---
app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- SAVE TO DB FUNCTION ---
async def save_file(message):
    try:
        # Detect any media
        media = message.video or message.document or message.photo or message.audio
        if not media:
            return

        if isinstance(media, list): media = media[-1] # For photos
        
        file_name = getattr(media, "file_name", None)
        if not file_name:
            file_name = message.caption or f"file_{message.id}"
        
        file_data = {
            "msg_id": message.id,
            "name": file_name,
            "type": message.media.value,
            "size": getattr(media, "file_size", 0)
        }
        
        await collection.update_one({"msg_id": message.id}, {"$set": file_data}, upsert=True)
        log(f"✅ DATABASE UPDATED: {file_name}")
    except Exception as e:
        log(f"❌ DB SAVE ERROR: {e}")

# --- UNIVERSAL MESSAGE LISTENER (DEBUG MODE) ---

@app.on_message()
async def global_listener(client, message):
    # This will log EVERY message the bot sees from anywhere
    chat_id = message.chat.id
    log(f"📩 RECEIVED: ChatID={chat_id} | Media={bool(message.media)} | Text='{message.text}'")

    # If it matches your channel, save it
    if chat_id == CHANNEL_ID:
        log("🎯 MATCH FOUND: This is your channel! Processing...")
        if message.media:
            await save_file(message)
        else:
            log("ℹ️ No media found in this channel message. Skipping save.")
    
    # Handle /start in private
    if message.text == "/start":
        await message.reply_text(f"Bot is Alive!\n\nTarget Channel ID: `{CHANNEL_ID}`\nYour Current Chat ID: `{chat_id}`")

# --- WEB SERVER ROUTES ---

async def get_files(request):
    files = []
    cursor = collection.find().sort("msg_id", -1)
    async for doc in cursor:
        files.append({
            "id": doc["msg_id"],
            "name": doc["name"],
            "type": doc["type"],
            "url": f"/stream/{doc['msg_id']}"
        })
    return web.json_response(files)

async def stream_file(request):
    try:
        msg_id = int(request.match_info['msg_id'])
        msg = await app.get_messages(CHANNEL_ID, msg_id)
        media = getattr(msg, msg.media.value)
        if isinstance(media, list): media = media[-1]

        resp = web.StreamResponse(status=200, headers={
            'Content-Type': 'application/octet-stream',
            'Content-Length': str(media.file_size),
            'Content-Disposition': f'attachment; filename="{getattr(media, "file_name", "file")}"'
        })
        await resp.prepare(request)
        async for chunk in app.stream_media(media):
            await resp.write(chunk)
        return resp
    except Exception as e:
        log(f"❌ STREAM ERROR: {e}")
        return web.Response(status=404)

# --- STARTUP LOGIC ---

async def on_startup(app_web):
    log("🚀 Starting Bot Client...")
    try:
        await mongo_client.admin.command('ping')
        log("✅ DATABASE: Connected")
    except Exception as e:
        log(f"❌ DATABASE: Failed! {e}")

    await app.start()
    me = await app.get_me()
    log(f"✅ BOT ONLINE: @{me.username}")
    log(f"📡 MONITORING ID: {CHANNEL_ID}")

async def on_cleanup(app_web):
    log("🛑 Stopping...")
    await app.stop()

# --- RUN APP ---
if __name__ == "__main__":
    server = web.Application()
    server.on_startup.append(on_startup)
    server.on_cleanup.append(on_cleanup)

    cors = aiohttp_cors.setup(server, defaults={
        "*": aiohttp_cors.ResourceOptions(allow_credentials=True, expose_headers="*", allow_headers="*")
    })
    
    server.add_routes([
        web.get('/', lambda r: web.Response(text="Bot is Running Smoothly")),
        web.get('/api/files', get_files),
        web.get('/stream/{msg_id}', stream_file)
    ])
    
    for route in list(server.router.routes()):
        cors.add(route)

    log(f"🌍 Server starting on port {PORT}")
    web.run_app(server, port=PORT)
