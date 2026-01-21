import os
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.errors import RPCError
from aiohttp import web
import motor.motor_asyncio
import aiohttp_cors

# --- LOGGING FUNCTION --- #
def log(text):
    print(f"[LOG] {text}", flush=True)

# --- CONFIGURATION --- #
try:
    API_ID = int(os.environ.get("API_ID", 0))
    API_HASH = os.environ.get("API_HASH", "")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    # Ensure CHANNEL_ID is an integer and starts with -100
    CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
    MONGO_URL = os.environ.get("MONGO_URL", "")
    PORT = int(os.environ.get("PORT", 8000))
except Exception as e:
    log(f"Config Error: {e}")

# --- DATABASE --- #
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = mongo_client["Cluster0g"]
collection = db["files"]

# --- BOT CLIENT --- #
# use_cache=True helps with Peer ID resolution
app = Client("auto_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- SAVE TO DB FUNCTION --- #
async def save_to_db(message):
    media = None
    name = "Unknown"
    file_type = "unknown"
    
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
                log(f"✅ Saved File: {name} (ID: {message.id})")
            else:
                log(f"⚠️ File already exists: {name}")
        except Exception as e:
            log(f"❌ DB Error: {e}")

# --- BOT HANDLERS --- #

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    await message.reply_text(
        "👋 **Bot is Online!**\n\n"
        f"Connected to Channel ID: `{CHANNEL_ID}`\n"
        "Send files to the Channel to save them."
    )

@app.on_message(filters.chat(CHANNEL_ID) & filters.media)
async def channel_post_handler(client, message):
    log(f"📩 Media Update in Channel: {message.id}")
    await save_to_db(message)

# --- WEB SERVER HANDLERS --- #

async def api_get_files(request):
    files = []
    cursor = collection.find().sort("msg_id", -1).limit(100)
    async for doc in cursor:
        files.append({
            "id": doc["msg_id"],
            "name": doc["name"],
            "type": doc["type"],
            "url": f"/stream/{doc['msg_id']}"
        })
    return web.json_response(files)

async def stream_handler(request):
    try:
        msg_id = int(request.match_info['msg_id'])
        msg = await app.get_messages(CHANNEL_ID, msg_id)
        
        # Determine media type dynamically
        media = None
        for attr in ["video", "document", "photo", "audio"]:
            if getattr(msg, attr, None):
                media = getattr(msg, attr)
                break
        
        if not media: 
            return web.Response(status=404, text="Media not found")

        # Photo handling (Photos are lists in Pyrogram)
        if isinstance(media, list): media = media[-1]

        resp = web.StreamResponse(
            status=200, reason='OK', 
            headers={
                'Content-Type': getattr(media, 'mime_type', 'application/octet-stream'),
                'Content-Disposition': f'inline; filename="{getattr(media, "file_name", "file")}"',
                'Content-Length': str(getattr(media, 'file_size', 0))
            }
        )
        await resp.prepare(request)
        async for chunk in app.stream_media(media):
            await resp.write(chunk)
        return resp
    except Exception as e:
        log(f"Stream Error: {e}")
        return web.Response(status=404)

async def health_check(request):
    return web.Response(text="Bot is Running", status=200)

# --- STARTUP & SHUTDOWN LOGIC --- #

async def on_startup(app_web):
    log("🚀 Starting Bot Client...")
    await app.start()
    
    me = await app.get_me()
    log(f"✅ Bot Logged in as: @{me.username}")

    try:
        # Check if Channel is accessible
        chat = await app.get_chat(CHANNEL_ID)
        log(f"✅ CONNECTED TO: {chat.title} ({chat.id})")
    except RPCError as e:
        log(f"❌ PEER ERROR: {e}")
        log("💡 FIX: 1. Add Bot to Channel. 2. Make Bot Admin. 3. Post a message in the channel.")

async def on_cleanup(app_web):
    log("🛑 Stopping Bot...")
    await app.stop()

# --- MAIN ENTRY POINT --- #

if __name__ == "__main__":
    server = web.Application()
    
    server.on_startup.append(on_startup)
    server.on_cleanup.append(on_cleanup)

    # CORS Setup
    cors = aiohttp_cors.setup(server, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True, expose_headers="*", allow_headers="*",
        )
    })
    
    server.add_routes([
        web.get('/', health_check),
        web.get('/api/files', api_get_files),
        web.get('/stream/{msg_id}', stream_handler)
    ])
    
    for route in list(server.router.routes()):
        cors.add(route)

    log(f"🌍 Starting Web Server on Port {PORT}")
    web.run_app(server, port=PORT)
