import os
import asyncio
from pyrogram import Client, filters
from aiohttp import web
import motor.motor_asyncio
import aiohttp_cors

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
MONGO_URL = os.environ.get("MONGO_URL", "")

# --- DB SETUP ---
client_db = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = client_db["Cluster0g"]
collection = db["files"]

# --- BOT CLIENT ---
app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- SAVE TO DB ---
async def save_file(message):
    media = message.video or message.document or message.photo or message.audio
    if media:
        if isinstance(media, list): media = media[-1] # For photos
        file_name = getattr(media, "file_name", message.caption or f"file_{message.id}")
        file_data = {
            "msg_id": message.id,
            "name": file_name,
            "type": message.media.value,
            "size": getattr(media, "file_size", 0)
        }
        await collection.update_one({"msg_id": message.id}, {"$set": file_data}, upsert=True)
        print(f"[LOG] Saved: {file_name}")

# --- LISTENERS ---
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    await message.reply_text("Bot is Online! Channel monitor chalu hai.")

@app.on_message(filters.chat(CHANNEL_ID) & filters.media)
async def handle_channel(client, message):
    print(f"[LOG] Media received in Channel!")
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
    msg_id = int(request.match_info['msg_id'])
    try:
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
        return web.Response(text=str(e), status=404)

# --- SERVER STARTUP ---
async def on_startup(app_web):
    print("[LOG] Starting Bot...")
    await app.start()
    print("[LOG] Bot is Online!")

async def on_cleanup(app_web):
    await app.stop()

if __name__ == "__main__":
    server = web.Application()
    server.on_startup.append(on_startup)
    server.on_cleanup.append(on_cleanup)
    
    cors = aiohttp_cors.setup(server, defaults={"*": aiohttp_cors.ResourceOptions(allow_credentials=True, expose_headers="*", allow_headers="*")})
    server.add_routes([
        web.get('/', lambda r: web.Response(text="Bot Running")),
        web.get('/api/files', get_files),
        web.get('/stream/{msg_id}', stream_file)
    ])
    for route in list(server.router.routes()): cors.add(route)
    
    web.run_app(server, port=8000)
