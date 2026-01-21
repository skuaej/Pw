import os
import asyncio
from pyrogram import Client, filters
from aiohttp import web
import motor.motor_asyncio
import aiohttp_cors

# --- LOGGING ---
def log(text):
    print(f"[BOT_LOG] {text}", flush=True)

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
MONGO_URL = os.environ.get("MONGO_URL", "")

# --- DATABASE ---
log("🔄 DB Connecting...")
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = mongo_client["Cluster0g"]
collection = db["files"]

# --- BOT CLIENT ---
# Session ka naam change kar diya hai fresh start ke liye
app = Client("final_fix_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- UNIVERSAL MESSAGE LISTENER ---
@app.on_message()
async def all_messages(client, message):
    # DUNIYA KA KOI BHI MESSAGE AAYEGA TO YE PRINT HOGA
    log(f"📩 NEW MESSAGE: ChatID={message.chat.id} | User={message.from_user.id if message.from_user else 'None'}")
    
    # Reply test
    if message.text == "/start":
        await message.reply_text("Bhai main sahi mein zinda hoon! Channel monitor chalu hai.")

    # Channel ID Match Logic
    if message.chat.id == CHANNEL_ID:
        log("🎯 MATCH FOUND: Message is from your Channel!")
        if message.media:
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
            log(f"✅ DB UPDATED: {file_name}")

# --- WEB API ---
async def api_get_files(request):
    files = []
    async for doc in collection.find().sort("msg_id", -1):
        files.append({"id": doc["msg_id"], "name": doc["name"], "url": f"/stream/{doc['msg_id']}"})
    return web.json_response(files)

# --- STARTUP LOGIC ---
async def on_startup(app_web):
    log("🚀 Bot Starting...")
    await app.start()
    me = await app.get_me()
    log(f"✅ BOT ONLINE: @{me.username}")
    log(f"📡 TARGET CHANNEL ID: {CHANNEL_ID}")

async def on_cleanup(app_web):
    await app.stop()

# --- RUNNING APP ---
if __name__ == "__main__":
    server = web.Application()
    server.on_startup.append(on_startup)
    server.on_cleanup.append(on_cleanup)
    
    cors = aiohttp_cors.setup(server, defaults={
        "*": aiohttp_cors.ResourceOptions(allow_credentials=True, expose_headers="*", allow_headers="*")
    })
    
    server.add_routes([
        web.get('/', lambda r: web.Response(text="Bot Alive and Running!")),
        web.get('/api/files', api_get_files)
    ])
    
    for route in list(server.router.routes()):
        cors.add(route)

    log("🌍 Web Server starting on port 8000")
    web.run_app(server, port=8000)
