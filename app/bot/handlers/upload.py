from telegram import Update, Message
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import Forbidden

from app.shared import config
from app.shared.database import containers as db_containers
from app.shared.database import items as db_items
from app.shared.database import users as db_users
from app.shared.constants import AWAITING_ITEMS_FOR_UPLOAD
from app.bot import keyboards as kb

async def process_message_for_saving(message: Message) -> dict | None:
    """[معدل ومصحح] يعالج الرسائل لتحويلها إلى بيانات قابلة للحفظ بطريقة آمنة."""
    file_type, file_obj = None, None
    if message.document: (file_type, file_obj) = ('document', message.document)
    elif message.video: (file_type, file_obj) = ('video', message.video)
    elif message.photo: (file_type, file_obj) = ('photo', message.photo[-1])
    elif message.audio: (file_type, file_obj) = ('audio', message.audio)
    elif message.voice: (file_type, file_obj) = ('voice', message.voice)

    if file_type and file_obj:
        try:
            fwd_msg = await message.forward(chat_id=config.STORAGE_CHANNEL_ID)
        except Forbidden:
            print(f"Error: Bot is not an admin in the storage channel {config.STORAGE_CHANNEL_ID} or cannot forward messages.")
            # If we assume we must have a storage location, we should return None or raise Error.
            # But the user prompt says "Return a dictionary containing... storage_message_id... Set file_id to None...".
            # If forwarding fails, we probably shouldn't save the item as we can't store the location.
            return None
        
        fwd_file_obj = None
        if fwd_msg:
            # Extract file ID from the forwarded message (as requested by user "keep it")
            if file_type == 'document' and fwd_msg.document: fwd_file_obj = fwd_msg.document
            elif file_type == 'video' and fwd_msg.video: fwd_file_obj = fwd_msg.video
            elif file_type == 'photo' and fwd_msg.photo: fwd_file_obj = fwd_msg.photo[-1]
            elif file_type == 'audio' and fwd_msg.audio: fwd_file_obj = fwd_msg.audio
            elif file_type == 'voice' and fwd_msg.voice: fwd_file_obj = fwd_msg.voice

        if fwd_msg: # We just need the message_id and chat_id primarily, but file_id is also good.
            collected_data = {
                'item_name': getattr(file_obj, 'file_name', f'ملف_{file_type}'),
                'item_type': file_type,
                'content': message.caption,
                'file_unique_id': file_obj.file_unique_id,
                'file_id': fwd_file_obj.file_id if fwd_file_obj else None, # Keep file_id as requested
                'storage_message_id': fwd_msg.message_id,
                'storage_channel_id': fwd_msg.chat.id
            }
            return collected_data
        else:
            print(f"Could not forward message of type {file_type}")
            return None

    elif message.text:
        return {
            'item_name': f"رسالة: {message.text[:20]}...",
            'item_type': 'text',
            'content': message.text,
            'file_unique_id': None,
            'file_id': None,
            'storage_message_id': None, # Text messages are not forwarded to storage channel in this logic
            'storage_channel_id': None
        }
        
    return None

async def add_items_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    db_users.update_user_last_active(update.effective_user.id)
    
    container_id = int(query.data.split(':')[1])
    if not db_containers.container_exists(container_id):
        await query.answer("⚠️ عذرًا، يبدو أن هذا المجلد قد تم حذفه بالفعل.", show_alert=False)
        await query.message.delete()
        return ConversationHandler.END

    context.user_data['target_container_id'] = container_id
    context.user_data['previous_menu'] = f"container:{container_id}"
    await query.message.edit_text(text="*➕ وضع الإضافة*\n\nأرسل ملفاتك، صورك، أو رسائلك\. \nعند الانتهاء، اضغط /done لحفظها أو /cancel للإلغاء\.", parse_mode='MarkdownV2')
    return AWAITING_ITEMS_FOR_UPLOAD


async def collect_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if 'items_to_add_buffer' not in context.user_data:
        context.user_data['items_to_add_buffer'] = []
    context.user_data['items_to_add_buffer'].append(update.message)
    await update.message.reply_text("👍 تم الاستلام\. أرسل المزيد أو اضغط /done للحفظ\.", parse_mode='MarkdownV2')
    return AWAITING_ITEMS_FOR_UPLOAD

async def save_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    container_id = context.user_data.get('target_container_id')
    message_buffer = context.user_data.get('items_to_add_buffer', [])

    if not db_containers.container_exists(container_id):
        await update.message.reply_text("⚠️ عذرًا، يبدو أن المجلد الذي تحاول الحفظ فيه قد تم حذفه.")
        context.user_data.clear()
        return ConversationHandler.END

    if not message_buffer:
        await update.message.reply_text("⚠️ لم ترسل أي عناصر. تم الخروج من وضع الإضافة.", reply_markup=kb.back_button(f"container:{container_id}"))
    else:
        await update.message.reply_text(f"📥 جاري حفظ {len(message_buffer)} عنصر...")
        count = 0
        for msg in message_buffer:
            item_info = await process_message_for_saving(msg)
            if item_info:
                # Step A: Add item metadata
                item_id = db_items.add_item(
                    container_id=container_id,
                    user_id=user_id,
                    item_name=item_info['item_name'],
                    item_type=item_info['item_type'],
                    content=item_info['content'],
                    file_unique_id=item_info['file_unique_id'],
                    file_id=item_info['file_id']
                )

                if item_id:
                    # Step B: Add file location if available
                    if item_info.get('storage_message_id') and item_info.get('storage_channel_id'):
                        db_items.add_file_location(
                            item_id=item_id,
                            channel_id=item_info['storage_channel_id'],
                            message_id=item_info['storage_message_id']
                        )
                    count += 1
        
        await update.message.reply_text(f"✅ تم حفظ {count} عنصر بنجاح.", reply_markup=kb.back_button(f"container:{container_id}"))
        context.user_data.clear()
        return ConversationHandler.END
