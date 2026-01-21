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
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
MONGO_URL = os.environ.get("MONGO_URL", "")

# --- DATABASE SETUP ---
log("🔄 Connecting to MongoDB...")
try:
    mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
    db = mongo_client["Cluster0g"]
    collection = db["files"]
    log("✅ MongoDB Configuration Loaded.")
except Exception as e:
    log(f"❌ MongoDB Config Error: {e}")

# --- BOT CLIENT ---
app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- SAVE TO DB ---
async def save_file(message):
    try:
        media = message.video or message.document or message.photo or message.audio
        if media:
            if isinstance(media, list): media = media[-1] # Photo logic
            
            file_name = getattr(media, "file_name", message.caption or f"file_{message.id}")
            file_data = {
                "msg_id": message.id,
                "name": file_name,
                "type": message.media.value,
                "size": getattr(media, "file_size", 0)
            }
            
            await collection.update_one({"msg_id": message.id}, {"$set": file_data}, upsert=True)
            log(f"✅ Saved to DB: {file_name}")
    except Exception as e:
        log(f"❌ DB Save Error: {e}")

# --- BOT HANDLERS ---

@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    log(f"Received /start from {message.from_user.id}")
    await message.reply_text("👋 Bot is Online!\nSend files to your channel to see them on the website.")

@app.on_message(filters.chat(CHANNEL_ID) & filters.media)
async def channel_listener(client, message):
    log(f"📩 New Media in Channel! Message ID: {message.id}")
    await save_file(message)

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
        log(f"❌ Stream Error: {e}")
        return web.Response(status=404)

# --- STARTUP LOGIC ---

async def on_startup(app_web):
    log("🚀 Starting Bot...")
    
    # Check MongoDB Connection
    try:
        await mongo_client.admin.command('ping')
        log("✅ DATABASE CONNECTED SUCCESSFULLY!")
    except Exception as e:
        log(f"❌ DATABASE CONNECTION FAILED: {e}")

    await app.start()
    me = await app.get_me()
    log(f"✅ Bot Logged in as: @{me.username}")
    log(f"📡 Monitoring Channel ID: {CHANNEL_ID}")

async def on_cleanup(app_web):
    await app.stop()

# --- RUN APP ---
if __name__ == "__main__":
    server = web.Application()
    server.on_startup.append(on_startup)
    server.on_cleanup.append(on_cleanup)

    # CORS Setup
    cors = aiohttp_cors.setup(server, defaults={
        "*": aiohttp_cors.ResourceOptions(allow_credentials=True, expose_headers="*", allow_headers="*")
    })
    
    server.add_routes([
        web.get('/', lambda r: web.Response(text="Bot Alive")),
        web.get('/api/files', get_files),
        web.get('/stream/{msg_id}', stream_file)
    ])
    
    for route in list(server.router.routes()):
        cors.add(route)

    log("🌍 Web Server starting on port 8000")
    web.run_app(server, port=8000) import os
import asyncio
from pyrogram import Client, filters
from aiohttp import web
import motor.motor_asyncio
import aiohttp_cors

# --- LOGGING FUNCTION ---
def log(text):
    print(f"[BOT_LOG] {text}", flush=True)

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
MONGO_URL = os.environ.get("MONGO_URL", "")

# --- DATABASE SETUP ---
log("🔄 Connecting to MongoDB...")
try:
    mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
    db = mongo_client["my_database"]
    collection = db["files"]
    log("✅ MongoDB Configuration Loaded.")
except Exception as e:
    log(f"❌ MongoDB Config Error: {e}")

# --- BOT CLIENT ---
app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- SAVE TO DB ---
async def save_file(message):
    try:
        media = message.video or message.document or message.photo or message.audio
        if media:
            if isinstance(media, list): media = media[-1] # Photo logic
            
            file_name = getattr(media, "file_name", message.caption or f"file_{message.id}")
            file_data = {
                "msg_id": message.id,
                "name": file_name,
                "type": message.media.value,
                "size": getattr(media, "file_size", 0)
            }
            
            await collection.update_one({"msg_id": message.id}, {"$set": file_data}, upsert=True)
            log(f"✅ Saved to DB: {file_name}")
    except Exception as e:
        log(f"❌ DB Save Error: {e}")

# --- BOT HANDLERS ---

@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    log(f"Received /start from {message.from_user.id}")
    await message.reply_text("👋 Bot is Online!\nSend files to your channel to see them on the website.")

@app.on_message(filters.chat(CHANNEL_ID) & filters.media)
async def channel_listener(client, message):
    log(f"📩 New Media in Channel! Message ID: {message.id}")
    await save_file(message)

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
        log(f"❌ Stream Error: {e}")
        return web.Response(status=404)

# --- STARTUP LOGIC ---

async def on_startup(app_web):
    log("🚀 Starting Bot...")
    
    # Check MongoDB Connection
    try:
        await mongo_client.admin.command('ping')
        log("✅ DATABASE CONNECTED SUCCESSFULLY!")
    except Exception as e:
        log(f"❌ DATABASE CONNECTION FAILED: {e}")

    await app.start()
    me = await app.get_me()
    log(f"✅ Bot Logged in as: @{me.username}")
    log(f"📡 Monitoring Channel ID: {CHANNEL_ID}")

async def on_cleanup(app_web):
    await app.stop()

# --- RUN APP ---
if __name__ == "__main__":
    server = web.Application()
    server.on_startup.append(on_startup)
    server.on_cleanup.append(on_cleanup)

    # CORS Setup
    cors = aiohttp_cors.setup(server, defaults={
        "*": aiohttp_cors.ResourceOptions(allow_credentials=True, expose_headers="*", allow_headers="*")
    })
    
    server.add_routes([
        web.get('/', lambda r: web.Response(text="Bot Alive")),
        web.get('/api/files', get_files),
        web.get('/stream/{msg_id}', stream_file)
    ])
    
    for route in list(server.router.routes()):
        cors.add(route)

    log("🌍 Web Server starting on port 8000")
    web.run_app(server, port=8000)
