import os
from pyrogram import Client, filters
from aiohttp import web
import motor.motor_asyncio
import aiohttp_cors

# --- CONFIGURATION --- #
API_ID = int(os.environ.get("API_ID", 12345))
API_HASH = os.environ.get("API_HASH", "your_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_token")
# SAHI (RIGHT) - Default value 0 kar do
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
MONGO_URL = os.environ.get("MONGO_URL", "mongodb+srv://...") # Step 1 wala URL
PORT = int(os.environ.get("PORT", 8080))

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
        # Check agar pehle se database me hai
        exist = await collection.find_one({"msg_id": message.id})
        if not exist:
            file_data = {
                "msg_id": message.id,
                "name": name,
                "type": file_type,
                "size": media.file_size
            }
            await collection.insert_one(file_data)
            print(f"Saved: {name}")

# --- BOT EVENTS --- #

# 1. Start hote hi purani files scan karo (Last 50)
async def index_channel():
    print("Indexing channel...")
    async for msg in app.get_chat_history(CHANNEL_ID, limit=50):
        await save_to_db(msg)
    print("Indexing done!")

# 2. Jab bhi naya message aaye, DB me daalo
@app.on_message(filters.chat(CHANNEL_ID) & filters.media)
async def new_post(client, message):
    await save_to_db(message)

# --- WEB SERVER ROUTES --- #

# API jo Website ko Data degi
async def api_get_files(request):
    files = []
    # Latest 50 files nikalo
    cursor = collection.find().sort("msg_id", -1).limit(50)
    async for document in cursor:
        files.append({
            "id": document["msg_id"],
            "name": document["name"],
            "type": document["type"],
            "url": f"/stream/{document['msg_id']}" # Stream URL
        })
    return web.json_response(files)

# File Streamer (Video play karne ke liye)
async def stream_handler(request):
    try:
        msg_id = int(request.match_info['msg_id'])
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
    except Exception:
        return web.Response(status=404)

async def health(r): return web.Response(text="Running")

# --- MAIN RUNNER --- #
if __name__ == "__main__":
    app.start()
    app.loop.create_task(index_channel()) # Start indexing in background

    # Web Server setup with CORS (Zaroori hai website ke liye)
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
    
    # Enable CORS on routes
    for route in list(server.router.routes()):
        cors.add(route)

    web.run_app(server, port=PORT)
