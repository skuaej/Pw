import os
import asyncio
from pyrogram import Client, filters, enums
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
    CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
    MONGO_URL = os.environ.get("MONGO_URL", "")
    PORT = int(os.environ.get("PORT", 8000))
except Exception as e:
    log(f"Config Error: {e}")

# --- DATABASE --- #
log("Connecting to MongoDB...")
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = mongo_client["Cluster0g"]
collection = db["files"]

# --- BOT CLIENT --- #
app = Client("auto_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- SAVE TO DB FUNCTION --- #
async def save_to_db(message):
    media = None
    name = "Unknown"
    file_type = "unknown"
    
    if message.video:
        media = message.video
        name = message.video.file_name or "Video"
        file_type = "video"
    elif message.document:
        media = message.document
        name = message.document.file_name or "Document"
        file_type = "document"
    elif message.photo:
        media = message.photo
        name = "Photo"
        file_type = "image"

    if media:
        file_data = {
            "msg_id": message.id,
            "name": name,
            "type": file_type,
            "size": getattr(media, "file_size", 0)
        }
        await collection.update_one({"msg_id": message.id}, {"$set": file_data}, upsert=True)
        log(f"✅ Database Updated: {name}")

# --- BOT HANDLERS --- #

# 1. Test command in Private Chat
@app.on_message(filters.command("start") & filters.private)
async def start_private(client, message):
    log(f"User {message.from_user.id} sent /start")
    await message.reply_text(f"Bot is alive! Listening to Channel: `{CHANNEL_ID}`")

# 2. DEBUG: Log EVERYTHING the bot sees
@app.on_message()
async def debug_handler(client, message):
    log(f"Incoming msg from Chat ID: {message.chat.id}")
    if message.chat.id == CHANNEL_ID:
        if message.media:
            log(f"Found media in channel! Saving...")
            await save_to_db(message)
        else:
            log("Found message in channel but it has no media.")

# --- WEB SERVER HANDLERS --- #

async def api_get_files(request):
    files = []
    count = await collection.count_documents({})
    cursor = collection.find().sort("msg_id", -1).limit(100)
    async for doc in cursor:
        files.append({
            "id": doc["msg_id"],
            "name": doc["name"],
            "type": doc["type"],
            "url": f"/stream/{doc['msg_id']}"
        })
    return web.json_response({"total_in_db": count, "files": files})

async def health_check(request):
    return web.Response(text="Bot is running smoothly!", status=200)

async def stream_handler(request):
    try:
        msg_id = int(request.match_info['msg_id'])
        msg = await app.get_messages(CHANNEL_ID, msg_id)
        media = getattr(msg, msg.media.value) if msg.media else None
        if not media: return web.Response(status=404)
        
        resp = web.StreamResponse(status=200, headers={
            'Content-Type': getattr(media, 'mime_type', 'application/octet-stream'),
            'Content-Length': str(media.file_size)
        })
        await resp.prepare(request)
        async for chunk in app.stream_media(media):
            await resp.write(chunk)
        return resp
    except:
        return web.Response(status=404)

# --- STARTUP --- #

async def on_startup(app_web):
    await app.start()
    log("🚀 Bot is Online and searching for channel...")

async def on_cleanup(app_web):
    await app.stop()

if __name__ == "__main__":
    server = web.Application()
    server.on_startup.append(on_startup)
    server.on_cleanup.append(on_cleanup)
    
    cors = aiohttp_cors.setup(server, defaults={
        "*": aiohttp_cors.ResourceOptions(allow_credentials=True, expose_headers="*", allow_headers="*")
    })
    
    server.add_routes([
        web.get('/', health_check),
        web.get('/api/files', api_get_files),
        web.get('/stream/{msg_id}', stream_handler)
    ])
    for route in list(server.router.routes()): cors.add(route)

    web.run_app(server, port=PORT)
