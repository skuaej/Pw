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
    PORT = int(os.environ.get("PORT", 8080))
except Exception as e:
    log(f"Config Error: {e}")

# --- DATABASE --- #
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = mongo_client["my_website_db"]
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
            # Check agar file pehle se hai
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

# 1. Start Command (Testing ke liye)
@app.on_message(filters.command("start"))
async def start_command(client, message):
    log(f"Start command received from {message.from_user.first_name}")
    await message.reply_text(
        "👋 **Bot is Online!**\n\n"
        "I am connected to the Database.\n"
        "Send files to the Channel, I will Auto-Save them."
    )

# 2. Channel Listener
@app.on_message(filters.chat(CHANNEL_ID) & filters.media)
async def channel_post_handler(client, message):
    log(f"📩 New Media in Channel: {message.id}")
    await save_to_db(message)

# --- WEB SERVER HANDLERS --- #

async def api_get_files(request):
    files = []
    # Latest 100 files
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
        media = getattr(msg, msg.media.value) if msg.media else None
        
        if not media: return web.Response(status=404)

        resp = web.StreamResponse(
            status=200, reason='OK', 
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

async def health_check(request):
    return web.Response(text="Bot is Running", status=200)

# --- STARTUP & SHUTDOWN LOGIC --- #

async def on_startup(app_web):
    log("🚀 Starting Bot...")
    await app.start()
    
    # Check Admin Rights & Connection
    try:
        chat = await app.get_chat(CHANNEL_ID)
        log(f"✅ CONNECTED TO CHANNEL: {chat.title} ({chat.id})")
        
        # Check if Admin
        me = await app.get_chat_member(CHANNEL_ID, "me")
        if me.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            log("✅ Bot is ADMIN. Ready to save files.")
        else:
            log("⚠️ WARNING: Bot is NOT Admin! Make it Admin to read messages.")
            
    except Exception as e:
        log(f"❌ ERROR: Cannot access channel. Check CHANNEL_ID.\nError: {e}")

async def on_cleanup(app_web):
    log("🛑 Stopping Bot...")
    await app.stop()

# --- MAIN ENTRY POINT --- #

if __name__ == "__main__":
    # Web App Setup
    server = web.Application()
    
    # Ye line Bot ko Web Server ke saath start karegi
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
    
    # Run App
    web.run_app(server, port=PORT)
