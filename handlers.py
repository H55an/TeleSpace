# handlers.py

import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, Message
from telegram.ext import ContextTypes, ConversationHandler

import config
import database
from keyboards import build_main_menu_keyboard, build_section_view_keyboard 
from constants import *

# --- الدوال المساعدة ---
async def process_message_for_saving(message: Message) -> dict | None:
    # ... (هذه الدالة تبقى كما هي من الكود الذي قدمته)
    file_type, file_obj = None, None
    if message.document: (file_type, file_obj) = ('document', message.document)
    elif message.video: (file_type, file_obj) = ('video', message.video)
    elif message.photo: (file_type, file_obj) = ('photo', message.photo[-1])
    elif message.audio: (file_type, file_obj) = ('audio', message.audio)
    if file_type and file_obj:
        fwd_msg = await message.forward(chat_id=config.STORAGE_CHANNEL_ID)
        fwd_file_obj = fwd_msg.document or fwd_msg.video or fwd_msg.photo[-1] or fwd_msg.audio
        return {'item_name': getattr(file_obj, 'file_name', f'ملف_{file_type}'), 'item_type': file_type, 'content': message.caption, 'file_unique_id': file_obj.file_unique_id, 'file_id': fwd_file_obj.file_id}
    elif message.text:
        return {'item_name': f"رسالة: {message.text[:20]}...", 'item_type': 'text', 'content': message.text, 'file_unique_id': None, 'file_id': None}
    return None

# --- #[تعديل جوهري]: دالة العرض والإرسال الجديدة ---
async def view_and_send_folder_contents(update: Update, context: ContextTypes.DEFAULT_TYPE, folder_id: int, offset: int = 0):
    """
    تجلب وترسل دفعة من العناصر مباشرة، مع زر حذف تحت كل عنصر.
    """
    chat_id = update.effective_chat.id
    items_page, total_items = database.get_items_paginated(folder_id, limit=PAGE_SIZE, offset=offset)
    
    if not items_page and offset == 0:
        await context.bot.send_message(chat_id, "هذا المجلد فارغ.")
        return

    if not items_page:
        await context.bot.send_message(chat_id, "لا توجد عناصر أخرى لعرضها.")
        return
        
    await context.bot.send_message(chat_id, f"إرسال {len(items_page)} عناصر (من {offset + 1} إلى {total_items})...")
    
    for item in items_page:
        try:
            # 1. بناء زر الحذف الخاص بهذا العنصر
            keyboard = [[
                InlineKeyboardButton("🗑️ حذف هذا العنصر", callback_data=f"delete_prompt:{item['item_record_id']}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # 2. إرسال العنصر بالطريقة الصحيحة مع إرفاق زر الحذف
            item_type = item['item_type']
            content = item['content']
            file_id = item['file_id']
            
            sent_message = None
            if item_type == 'text':
                sent_message = await context.bot.send_message(chat_id=chat_id, text=content, reply_markup=reply_markup)
            else:
                if item_type == 'document': sent_message = await context.bot.send_document(chat_id=chat_id, document=file_id, caption=content, reply_markup=reply_markup)
                elif item_type == 'video': sent_message = await context.bot.send_video(chat_id=chat_id, video=file_id, caption=content, reply_markup=reply_markup)
                elif item_type == 'photo': sent_message = await context.bot.send_photo(chat_id=chat_id, photo=file_id, caption=content, reply_markup=reply_markup)
                elif item_type == 'audio': sent_message = await context.bot.send_audio(chat_id=chat_id, audio=file_id, caption=content, reply_markup=reply_markup)
            
            await asyncio.sleep(0.5) # تأخير بسيط
        except Exception as e:
            await context.bot.send_message(chat_id, f"لم يتم إرسال العنصر '{item['item_name']}'. الخطأ: {e}")
            
    # 3. بعد إرسال الدفعة، تحقق إذا كان هناك المزيد
    new_offset = offset + len(items_page)
    if new_offset < total_items:
        next_keyboard = [[InlineKeyboardButton(f"📥 عرض الـ {min(PAGE_SIZE, total_items - new_offset)} عناصر التالية", callback_data=f"view_files:{folder_id}:{new_offset}")]]
        await context.bot.send_message(chat_id, "لا يزال هناك المزيد من العناصر.", reply_markup=InlineKeyboardMarkup(next_keyboard))
    else:
        await context.bot.send_message(chat_id, "تم عرض كل العناصر في هذا المجلد.")


# --- دوال الواجهة الرئيسية والتصفح ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ... (تبقى كما هي من الكود الذي قدمته)
    user = update.effective_user
    database.add_user_if_not_exists(user_id=user.id, first_name=user.first_name)
    keyboard = build_main_menu_keyboard(user.id)
    reply_text = f"مرحبًا بك في TeleSpace .\n\nمساحتك الخاصة على تيليجرام لبناء بيئتك المثالية وتخصيصها بنفسك ، وتخزين كل ما يهمك من المحتوى (ملفات، رسائل، صور، وسائط) بطريقة منظمة ومرنة .\n\n🗂️ يمكنك إنشاء الأقسام والأقسام الفرعية .\n📂 يمكنك إنشاء المجلدات وتخزين ملفاتك فيها ."
    if update.message: await update.message.reply_html(reply_text, reply_markup=keyboard)
    elif update.callback_query:
        try: await update.callback_query.message.edit_text(reply_text, reply_markup=keyboard, parse_mode='HTML')
        except Exception: pass
    return ConversationHandler.END

async def button_press_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    
    # --- منطق التصفح ---
    if data.startswith("section:"):
        section_id = int(data.split(':')[1])
        keyboard = build_section_view_keyboard(section_id)
        await query.message.edit_text("اختر عنصرًا للتصفح أو `⚙️` للتحكم:", reply_markup=keyboard)
        
    elif data == "back_to_main":
        await start(update, context)

    # #[تعديل 1]: عند الضغط على اسم المجلد، نعرض خيارات التصفح فقط
    elif data.startswith("folder:"):
        folder_id = int(data.split(':')[1])
        keyboard = [
            [InlineKeyboardButton("📂 عرض المحتويات", callback_data=f"view_files:{folder_id}:0")],
            [InlineKeyboardButton("➕ إضافة عناصر", callback_data=f"add_files_to:{folder_id}")],
            [InlineKeyboardButton("🔙 العودة", callback_data="back_to_main")] # يمكن تحسينه لاحقًا ليعود للقسم الأب
        ]
        await query.message.edit_text("اختر الإجراء:", reply_markup=InlineKeyboardMarkup(keyboard))

    # --- منطق قوائم الإعدادات ---
    elif data.startswith("settings_section:"):
        section_id = int(data.split(':')[1])
        keyboard = [
            # [InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"rename_section:{section_id}")],
            [InlineKeyboardButton("🗑️ حذف القسم بالكامل", callback_data=f"delete_section_prompt:{section_id}")],
            [InlineKeyboardButton("🔙 عودة", callback_data="back_to_main")] # يعود للقائمة الرئيسية
        ]
        await query.message.edit_text("خيارات التحكم بالقسم:", reply_markup=InlineKeyboardMarkup(keyboard))

    # #[تعديل 2]: عند الضغط على زر الإعدادات، نعرض خيارات الإدارة
    elif data.startswith("settings_folder:"):
        folder_id = int(data.split(':')[1])
        keyboard = [
            # [InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"rename_folder:{folder_id}")],
            [InlineKeyboardButton("🔥 حذف كل المحتويات فقط", callback_data=f"delete_all_prompt:{folder_id}")],
            [InlineKeyboardButton("🗑️ حذف المجلد بالكامل", callback_data=f"delete_folder_prompt:{folder_id}")],
            [InlineKeyboardButton("🔙 عودة", callback_data="back_to_main")] 
        ]
        await query.message.edit_text("خيارات التحكم بالمجلد:", reply_markup=InlineKeyboardMarkup(keyboard))

    # --- منطق عرض وحذف المحتويات (يبقى كما هو) ---
    elif data.startswith("view_files:"):
        _, folder_id, offset = data.split(':')
        await view_and_send_folder_contents(update, context, int(folder_id), int(offset))
    
    # ... (بقية منطق الحذف الفردي وحذف المجلدات والأقسام يبقى كما هو تمامًا)
    elif data.startswith("delete_prompt:"):
        item_id = int(data.split(':')[1])
        text = "⚠️ هل أنت متأكد من أنك تريد حذف هذا العنصر بشكل دائم؟"
        keyboard = [[InlineKeyboardButton("✅ نعم، احذف", callback_data=f"delete_confirm:{item_id}"), InlineKeyboardButton("❌ لا، تراجع", callback_data="delete_cancel")]]
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("delete_confirm:"):
        item_id = int(data.split(':')[1])
        database.delete_item(item_id)
        await query.message.edit_text(text="✅ تم حذف العنصر بنجاح.")
    elif data == "delete_cancel":
        await query.message.delete()
        
    elif data.startswith("delete_folder_prompt:"):
        folder_id = int(data.split(':')[1])
        text = "⚠️ **تحذير!**\nهل تريد بالتأكيد حذف هذا المجلد **وكل محتوياته** بشكل دائم؟"
        keyboard = [[
            InlineKeyboardButton("✅ نعم، احذف المجلد", callback_data=f"delete_folder_confirm:{folder_id}"),
            InlineKeyboardButton("❌ لا، تراجع", callback_data=f"settings_folder:{folder_id}")
        ]]
        await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    elif data.startswith("delete_folder_confirm:"):
        folder_id = int(data.split(':')[1])
        database.delete_folder(folder_id)
        await query.answer("✅ تم حذف المجلد بنجاح!")
        await start(update, context)

    elif data.startswith("delete_section_prompt:"):
        section_id = int(data.split(':')[1])
        text = "🔥 **تحذير خطير جدا!**\nهل تريد بالتأكيد حذف هذا القسم **وكل ما بداخله** بشكل دائم؟"
        keyboard = [[
            InlineKeyboardButton("🔥 نعم، متأكد تمامًا", callback_data=f"delete_section_confirm:{section_id}"),
            InlineKeyboardButton("❌ لا، تراجع", callback_data=f"settings_section:{section_id}")
        ]]
        await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    elif data.startswith("delete_section_confirm:"):
        section_id = int(data.split(':')[1])
        database.delete_section_recursively(section_id)
        await query.answer("✅ تم حذف القسم وكل محتوياته بنجاح!")
        await start(update, context)

    # --- #[إضافة جديدة]: منطق حذف كل المحتويات ---
    elif data.startswith("delete_all_prompt:"):
        folder_id = int(data.split(':')[1])
        text = "⚠️ **تحذير!**\nهل تريد بالتأكيد حذف **كل محتويات** هذا المجلد (سيبقى المجلد فارغًا)؟"
        keyboard = [[
            InlineKeyboardButton("✅ نعم، احذف المحتويات", callback_data=f"delete_all_confirm:{folder_id}"),
            InlineKeyboardButton("❌ لا، تراجع", callback_data=f"settings_folder:{folder_id}")
        ]]
        await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    
    elif data.startswith("delete_all_confirm:"):
        folder_id = int(data.split(':')[1])
        deleted_count = database.delete_all_items_in_folder(folder_id)
        await query.message.edit_text(f"✅ تم حذف {deleted_count} عنصر بنجاح. المجلد الآن فارغ.")



# --- دوال المحادثات (تبقى كما هي تمامًا من الكود الذي قدمته) ---
async def new_section_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer(); data = query.data
    parent_id = int(data.split(':')[1]) if data.startswith("new_section_sub:") else None
    context.user_data['parent_section_id'] = parent_id
    await query.message.edit_text(text="يرجى إرسال اسم القسم الجديد:"); return AWAITING_SECTION_NAME
async def receive_section_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user; section_name = update.message.text
    parent_id = context.user_data.get('parent_section_id')
    database.add_section(user_id=user.id, section_name=section_name, parent_section_id=parent_id)
    await update.message.reply_text(f"✅ تم إنشاء قسم '{section_name}' بنجاح!")
    context.user_data.clear(); await start(update, context); return ConversationHandler.END
async def new_folder_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer(); data = query.data
    parent_section_id = int(data.split(':')[1]) if data.startswith("new_folder_in_sec:") else None
    context.user_data['parent_section_id_for_folder'] = parent_section_id
    await query.message.edit_text(text="يرجى إرسال اسم المجلد الجديد:"); return AWAITING_FOLDER_NAME
async def receive_folder_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user; folder_name = update.message.text
    parent_section_id = context.user_data.get('parent_section_id_for_folder')
    database.add_folder(owner_user_id=user.id, folder_name=folder_name, section_id=parent_section_id)
    await update.message.reply_text(f"✅ تم إنشاء مجلد '{folder_name}' بنجاح!")
    context.user_data.clear(); await start(update, context); return ConversationHandler.END
async def add_files_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer(); folder_id = int(query.data.split(':')[1])
    context.user_data['target_folder_id'] = folder_id; context.user_data['files_to_add_buffer'] = []
    await query.message.edit_text(text="أنت الآن في وضع الإضافة.\n\nأرسل أي عدد من العناصر. عندما تنتهي، أرسل كلمة `حفظ`.")
    return AWAITING_FILES_FOR_UPLOAD
async def collect_files_and_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message_text = update.message.text
    if message_text and message_text.lower() == "حفظ":
        target_folder_id = context.user_data.get('target_folder_id')
        message_buffer = context.user_data.get('files_to_add_buffer', [])
        if not message_buffer:
            await update.message.reply_text("لم يتم إرسال أي عناصر للحفظ."); context.user_data.clear(); await start(update, context); return ConversationHandler.END
        await update.message.reply_text(f"جاري حفظ {len(message_buffer)} عنصر...")
        count = 0
        for msg in message_buffer:
            item_info = await process_message_for_saving(msg)
            if item_info:
                database.add_item(
                    folder_id=target_folder_id, item_name=item_info['item_name'], item_type=item_info['item_type'],
                    content=item_info['content'], file_unique_id=item_info['file_unique_id'], file_id=item_info['file_id']
                )
                count += 1
        await update.message.reply_text(f"✅ تم حفظ {count} عنصر بنجاح!")
        context.user_data.clear(); await start(update, context); return ConversationHandler.END
    else:
        context.user_data.get('files_to_add_buffer', []).append(update.message)
        await update.message.reply_text("👍 تم الاستلام. أرسل المزيد أو أرسل `حفظ`.")
        return AWAITING_FILES_FOR_UPLOAD
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear(); await update.message.reply_text("تم إلغاء العملية."); await start(update, context)
    return ConversationHandler.END

