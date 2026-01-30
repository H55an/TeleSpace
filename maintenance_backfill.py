import asyncio
import os
import psycopg2
import psycopg2.extras
from telegram import Bot
from app.shared import config

# Ensure directories exist
os.makedirs('static/thumbnails', exist_ok=True)
os.makedirs('static/profiles', exist_ok=True)

async def backfill_metadata():
    print("Starting backfill process...")
    
    # 1. Connect to DB
    conn = psycopg2.connect(config.DATABASE_URL)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # 2. Get items that need update (file_size IS NULL is a good indicator of old items)
    print("Fetching items to update...")
    cursor.execute("""
        SELECT i.item_record_id, fl.channel_id, fl.message_id
        FROM items i
        JOIN file_locations fl ON i.item_record_id = fl.item_id
        WHERE i.file_size IS NULL
    """)
    items_to_process = cursor.fetchall()
    print(f"Found {len(items_to_process)} items to process.")
    
    # 3. Initialize Bot
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN, base_url=config.LOCAL_API_URL, base_file_url=config.LOCAL_FILE_URL)
    
    count = 0
    for item in items_to_process:
        item_id = item['item_record_id']
        chat_id = item['channel_id']
        msg_id = item['message_id']
        
        try:
            # Fetch message from storage channel
            # Note: get_messages might not be available in simple Bot class depending on version, 
            # usually it is usable via get_chat then get_message? 
            # python-telegram-bot wrapper usually doesn't have get_message(s) directly on Bot except for recent versions?
            # Actually, standard Bot API doesn't have getMessage. We rely on Forwarding usually.
            # BUT, since we are the admin of the channel, we might not be able to "get" it easily without a user involvement 
            # OR we simply can't "get" a message by ID via Bot API unless we forward it.
            # WAIT. The user prompt says: "Use channel_id and message_id to call getMessages (or similar)..."
            # Bot API DOES NOT have getMessage. 
            # However, MTProto (Telethon/Pyrogram) DOES.
            # Using standard Bot API, we can try to copyMessage (sendCopy) to a private chat with the bot itself?
            # Or forwardMessage.
            # Let's try forwarding it to the archival channel again (or a temporary chat) to read it?
            # NO, that duplicates it.
            # 
            # Actually, standard Bot API has NO Way to get a message history.
            # UNLESS the user implies we use a library that supports it.
            # But we are using python-telegram-bot.
            # 
            # Workaround: Forward the message to the bot (or a specific dump chat), analyze it, then delete the forward.
            # Let's forward it to the STORAGE_CHANNEL_ID (itself? no) or to the bot's private chat? 
            # Bots cannot message themselves.
            # 
            # Let's assuming we can forward it to a "dump" channel or maybe just re-analysing isn't possible with just Bot API without Forwarding.
            # 
            # Let's try forwarding to the Storage Channel again? It will create a NEW message. We don't want that.
            # 
            # Actually, if we use `bot.forward_message` to a dummy chat ID (e.g. the admin's ID if known, or a log channel), we can read the resulting Message object.
            # Let's assume we have a LOG_CHANNEL_ID or just use STORAGE_CHANNEL_ID but delete it immediately.
            # Risk: Deleting messages in channel might not be desired.
            # 
            # Let's try to forward to the Storage Channel, read metadata, then delete the COPY.
            # Yes, that works.
            
            # Forwarding to the same channel
            dummy_msg = await bot.forward_message(chat_id=config.STORAGE_CHANNEL_ID, from_chat_id=chat_id, message_id=msg_id)
            
            if dummy_msg:
                # Extract Data
                file_obj = None
                file_type = 'unknown'
                
                if dummy_msg.document: (file_type, file_obj) = ('document', dummy_msg.document)
                elif dummy_msg.video: (file_type, file_obj) = ('video', dummy_msg.video)
                elif dummy_msg.photo: (file_type, file_obj) = ('photo', dummy_msg.photo[-1])
                elif dummy_msg.audio: (file_type, file_obj) = ('audio', dummy_msg.audio)
                elif dummy_msg.voice: (file_type, file_obj) = ('voice', dummy_msg.voice)
                
                if file_obj:
                    # Update DB
                    file_name = getattr(file_obj, 'file_name', f'{file_type}_{file_obj.file_unique_id}')
                    mime_type = getattr(file_obj, 'mime_type', None)
                    file_size = getattr(file_obj, 'file_size', 0)
                    width = getattr(file_obj, 'width', None)
                    height = getattr(file_obj, 'height', None)
                    duration = getattr(file_obj, 'duration', None)
                    thumbnail_path = None
                    
                    # Thumb processing
                    thumb = getattr(file_obj, 'thumbnail', None) or getattr(file_obj, 'thumb', None)
                    if thumb:
                        try:
                            filename = f"{file_obj.file_unique_id}.jpg"
                            save_path = os.path.join(os.getcwd(), 'static', 'thumbnails', filename)
                            
                            # Check if already exists
                            if not os.path.exists(save_path):
                                thumb_file = await bot.get_file(thumb.file_id)
                                await thumb_file.download_to_drive(save_path)
                            
                            thumbnail_path = f"static/thumbnails/{filename}"
                        except Exception as e:
                            print(f"Error downloading thumb for {item_id}: {e}")

                    # Update SQL
                    update_query = """
                        UPDATE items SET
                            file_name = %s,
                            mime_type = %s,
                            file_size = %s,
                            width = %s,
                            height = %s,
                            duration = %s,
                            thumbnail_path = %s
                        WHERE item_record_id = %s
                    """
                    cursor.execute(update_query, (file_name, mime_type, file_size, width, height, duration, thumbnail_path, item_id))
                    conn.commit()
                    count += 1
                    print(f"Updated item {item_id}")
                
                # Delete the dummy forward
                try:
                    await bot.delete_message(chat_id=dummy_msg.chat.id, message_id=dummy_msg.message_id)
                except:
                    pass
            
        except Exception as e:
            print(f"Failed to process item {item_id}: {e}")
            conn.rollback()
            
    print(f"Backfill complete. Updated {count} items.")
    cursor.close()
    conn.close()

if __name__ == "__main__":
    asyncio.run(backfill_metadata())
