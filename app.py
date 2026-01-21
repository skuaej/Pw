import os
import asyncio
from pyrogram import Client, filters
from aiohttp import web
import motor.motor_asyncio
import aiohttp_cors

# --- LOGGING ---
def log(text):
    print(f"[DEBUG_LOG] {text}", flush=True)

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
MONGO_URL = os.environ.get("MONGO_URL", "")

# --- DB ---
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = mongo_client["my_database"]
collection = db["files"]

# --- BOT CLIENT (Name changed to force fresh session) ---
app = Client("fresh_test_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- THE ONLY LISTENER ---
@app.on_message()
async def on_any_message(client, message):
    # DUNIYA KA KOI BHI MESSAGE AAYEGA TO YE LOG HONA CHAHIYE
    log(f"🔥 MESSAGE MIL GAYA! | Chat ID: {message.chat.id} | From: {message.from_user.id if message.from_user else 'Channel'}")
    
    # Reply test
    if message.text == "/start":
        await message.reply_text("Bhai main sahi mein zinda hoon!")

    # Channel Save Logic
    if message.chat.id == CHANNEL_ID and message.media:
        media = message.video or message.document or message.photo or message.audio
        if isinstance(media, list): media = media[-1]
        file_name = getattr(media, "file_name", f"file_{message.id}")
        
        await collection.update_one(
            {"msg_id": message.id},
            {"$set": {
                "msg_id": message.id,
                "name": file_name,
                "type": message.media.value,
                "size": getattr(media, "file_size", 0)
            }},
            upsert=True
        )
        log(f"✅ DB MEIN SAVE HUA: {file_name}")

# --- WEB SERVER ---
async def api_files(request):
    files = []
    async for doc in collection.find().sort("msg_id", -1):
        files.append({"id": doc["msg_id"], "name": doc["name"], "url": f"/stream/{doc['msg_id']}"})
    return web.json_response(files)

async def on_startup(app_web):
    log("🚀 Bot Starting...")
    await app.start()
    # Force delete any previous webhook to start polling
    await app.delete_webhook(drop_pending_updates=True)
    me = await app.get_me()
    log(f"✅ BOT READY: @{me.username}")

# --- RUN ---
if __name__ == "__main__":
    server = web.Application()
    server.on_startup.append(on_startup)
    cors = aiohttp_cors.setup(server, defaults={"*": aiohttp_cors.ResourceOptions(allow_credentials=True, expose_headers="*", allow_headers="*")})
    server.add_routes([
        web.get('/api/files', api_get_files if 'api_get_files' in globals() else api_files),
        web.get('/', lambda r: web.Response(text="Running"))
    ])
    for route in list(server.router.routes()): cors.add(route)
    web.run_app(server, port=8000)
