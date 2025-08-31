# main.py

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters
)

import config
from database import (
    add_user_if_not_exists,
    add_section, get_root_sections, get_subsections,
    add_folder, get_root_folders, get_folders_in_section,
    add_file, get_files_paginated, get_all_user_folders
)

# --- #[الإصلاح هنا 1]: تعريف الثوابت في بداية الملف ---
PAGE_SIZE = 10 # عدد الملفات في كل دفعة

# --- تعريف حالات المحادثة ---
(AWAITING_SECTION_NAME, AWAITING_FOLDER_NAME, AWAITING_SAVE_LOCATION) = range(3)

# --- الدوال المساعدة ---
async def forward_file_to_storage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> dict | None:
    # ... (هذه الدالة تبقى كما هي)
    try:
        message = update.message
        forwarded_message = await message.forward(chat_id=config.STORAGE_CHANNEL_ID)
        file_type, file_obj = None, None
        if forwarded_message.document: (file_type, file_obj) = ('document', forwarded_message.document)
        elif forwarded_message.video: (file_type, file_obj) = ('video', forwarded_message.video)
        elif forwarded_message.photo: (file_type, file_obj) = ('photo', forwarded_message.photo[-1])
        elif forwarded_message.audio: (file_type, file_obj) = ('audio', forwarded_message.audio)
        if file_obj and file_type:
            return {
                'file_unique_id': file_obj.file_unique_id,
                'file_id': file_obj.file_id,
                'file_name': getattr(file_obj, 'file_name', f'ملف_{file_type}'),
                'file_type': file_type,
                'caption': message.caption
            }
    except Exception as e:
        print(f"حدث خطأ أثناء إعادة توجيه الملف: {e}")
    return None

async def send_files_paginated(update: Update, context: ContextTypes.DEFAULT_TYPE, folder_id: int, offset: int = 0):
    """ تجلب وترسل دفعة من الملفات من مجلد معين. """
    query = update.callback_query
    chat_id = update.effective_chat.id
    
    # #[الإصلاح هنا 2]: الدالة الآن تستخدم الثابت المعرف في الأعلى
    files_page, total_files = get_files_paginated(folder_id, limit=PAGE_SIZE, offset=offset)

    if not files_page and offset == 0:
        await context.bot.send_message(chat_id, "هذا المجلد فارغ.")
        await start(update, context)
        return

    if not files_page:
        await context.bot.send_message(chat_id, "لا توجد ملفات أخرى لعرضها.")
        return

    await context.bot.send_message(chat_id, f"إرسال {len(files_page)} ملفات (من {offset + 1} إلى {total_files})...")
    for file in files_page:
        try:
            file_id, file_type, caption = file['file_id'], file['file_type'], file['caption']
            if file_type == 'document': await context.bot.send_document(chat_id=chat_id, document=file_id, caption=caption)
            elif file_type == 'video': await context.bot.send_video(chat_id=chat_id, video=file_id, caption=caption)
            elif file_type == 'photo': await context.bot.send_photo(chat_id=chat_id, photo=file_id, caption=caption)
            elif file_type == 'audio': await context.bot.send_audio(chat_id=chat_id, audio=file_id, caption=caption)
            await asyncio.sleep(0.5)
        except Exception as e:
            await context.bot.send_message(chat_id, f"لم يتم إرسال الملف '{file['file_name']}'. الخطأ: {e}")

    new_offset = offset + PAGE_SIZE
    if new_offset < total_files:
        keyboard = [[InlineKeyboardButton(f"📥 إرسال الـ {min(PAGE_SIZE, total_files - new_offset)} ملفات التالية", callback_data=f"next_files:{folder_id}:{new_offset}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id, "لا يزال هناك المزيد من الملفات.", reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id, "تم إرسال كل الملفات في هذا المجلد.")

# ... (بقية الكود يبقى كما هو تمامًا) ...
# (start, build_main_menu_keyboard, button_press_router,
# new_section_prompt, receive_section_name, new_folder_prompt, receive_folder_name,
# file_received_handler, save_location_selected, cancel_conversation, main)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    add_user_if_not_exists(user_id=user.id, first_name=user.first_name)
    keyboard = build_main_menu_keyboard(user.id)
    reply_text = "🗂️ **الواجهة الرئيسية**\n\nاختر قسمًا أو مجلدًا للتصفح."
    if update.message:
        await update.message.reply_html(reply_text, reply_markup=keyboard)
    elif update.callback_query:
        try:
            await update.callback_query.message.edit_text(reply_text, reply_markup=keyboard, parse_mode='HTML')
        except Exception:
            pass
    return ConversationHandler.END
def build_main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    keyboard_layout = []
    root_sections = get_root_sections(user_id)
    if root_sections:
        keyboard_layout.append([InlineKeyboardButton(f"📂 {s['section_name']}", callback_data=f"section:{s['section_id']}") for s in root_sections])
    root_folders = get_root_folders(user_id)
    if root_folders:
        keyboard_layout.append([InlineKeyboardButton(f"📁 {f['folder_name']}", callback_data=f"folder:{f['folder_id']}") for f in root_folders])
    control_buttons = [
        InlineKeyboardButton("➕ قسم رئيسي", callback_data="new_section_root"),
        InlineKeyboardButton("➕ مجلد رئيسي", callback_data="new_folder_root")
    ]
    keyboard_layout.append(control_buttons)
    return InlineKeyboardMarkup(keyboard_layout)
async def button_press_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("section:"):
        section_id = int(data.split(':')[1])
        keyboard_layout = []
        subsections = get_subsections(section_id)
        if subsections:
            keyboard_layout.append([InlineKeyboardButton(f"📂 {s['section_name']}", callback_data=f"section:{s['section_id']}") for s in subsections])
        folders_in_section = get_folders_in_section(section_id)
        if folders_in_section:
            keyboard_layout.append([InlineKeyboardButton(f"📁 {f['folder_name']}", callback_data=f"folder:{f['folder_id']}") for f in folders_in_section])
        control_buttons = [
            InlineKeyboardButton("➕ قسم فرعي هنا", callback_data=f"new_section_sub:{section_id}"),
            InlineKeyboardButton("➕ مجلد جديد هنا", callback_data=f"new_folder_in_sec:{section_id}")
        ]
        keyboard_layout.append(control_buttons)
        keyboard_layout.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")])
        reply_markup = InlineKeyboardMarkup(keyboard_layout)
        await query.message.edit_text("اختر قسمًا فرعيًا أو مجلدًا:", reply_markup=reply_markup)
    elif data.startswith("folder:"):
        folder_id = int(data.split(':')[1])
        await query.delete_message()
        await send_files_paginated(update, context, folder_id, offset=0)
    elif data.startswith("next_files:"):
        _, folder_id, offset = data.split(':')
        await query.delete_message()
        await send_files_paginated(update, context, int(folder_id), int(offset))
    elif data == "back_to_main":
        await start(update, context)
async def new_section_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    parent_id = None
    if data.startswith("new_section_sub:"):
        parent_id = int(data.split(':')[1])
    context.user_data['parent_section_id'] = parent_id
    await query.message.edit_text(text="يرجى إرسال اسم القسم الجديد:")
    return AWAITING_SECTION_NAME
async def receive_section_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    section_name = update.message.text
    parent_id = context.user_data.get('parent_section_id')
    add_section(user_id=user.id, section_name=section_name, parent_section_id=parent_id)
    await update.message.reply_text(f"✅ تم إنشاء قسم '{section_name}' بنجاح!")
    context.user_data.clear()
    await start(update, context)
    return ConversationHandler.END
async def new_folder_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    parent_section_id = None
    if data.startswith("new_folder_in_sec:"):
        parent_section_id = int(data.split(':')[1])
    context.user_data['parent_section_id_for_folder'] = parent_section_id
    await query.message.edit_text(text="يرجى إرسال اسم المجلد الجديد:")
    return AWAITING_FOLDER_NAME
async def receive_folder_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    folder_name = update.message.text
    parent_section_id = context.user_data.get('parent_section_id_for_folder')
    add_folder(owner_user_id=user.id, folder_name=folder_name, section_id=parent_section_id)
    await update.message.reply_text(f"✅ تم إنشاء مجلد '{folder_name}' بنجاح!")
    context.user_data.clear()
    await start(update, context)
    return ConversationHandler.END
async def file_received_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    file_info = await forward_file_to_storage(update, context)
    if not file_info:
        await update.message.reply_text("عذرًا، حدث خطأ أثناء معالجة الملف.")
        return ConversationHandler.END
    context.user_data['file_to_save'] = file_info
    keyboard = []
    all_folders = get_all_user_folders(user_id)
    if not all_folders:
        await update.message.reply_text("ليس لديك أي مجلدات بعد. يرجى إنشاء مجلد أولاً.")
        return ConversationHandler.END
    for folder in all_folders:
        display_name = f"📁 {folder['folder_name']}"
        if folder['section_name']:
            display_name += f" (قسم: {folder['section_name']})"
        keyboard.append([InlineKeyboardButton(display_name, callback_data=f"save_to_folder:{folder['folder_id']}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("تم استلام الملف بنجاح. أين تريد حفظه؟", reply_markup=reply_markup)
    return AWAITING_SAVE_LOCATION
async def save_location_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    folder_id = int(query.data.split(':')[1])
    file_info = context.user_data.get('file_to_save')
    if not file_info:
        await query.edit_message_text("عذرًا، يبدو أن معلومات الملف قد ضاعت. يرجى إرسال الملف مرة أخرى.")
        return ConversationHandler.END
    add_file(
        folder_id=folder_id,
        file_unique_id=file_info['file_unique_id'],
        file_id=file_info['file_id'],
        file_name=file_info['file_name'],
        file_type=file_info['file_type'],
        caption=file_info['caption']
    )
    await query.edit_message_text(f"✅ تم حفظ الملف بنجاح!")
    context.user_data.clear()
    return ConversationHandler.END
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("تم إلغاء العملية.")
    await start(update, context)
    return ConversationHandler.END
def main() -> None:
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    save_file_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO, file_received_handler)],
        states={AWAITING_SAVE_LOCATION: [CallbackQueryHandler(save_location_selected, pattern="^save_to_folder:")]},
        fallbacks=[CommandHandler("cancel", cancel_conversation), CommandHandler("start", start)],
    )
    section_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_section_prompt, pattern="^new_section_root$"), CallbackQueryHandler(new_section_prompt, pattern="^new_section_sub:")],
        states={AWAITING_SECTION_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_section_name)]},
        fallbacks=[CommandHandler("cancel", cancel_conversation)]
    )
    folder_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_folder_prompt, pattern="^new_folder_root$"), CallbackQueryHandler(new_folder_prompt, pattern="^new_folder_in_sec:")],
        states={AWAITING_FOLDER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_folder_name)]},
        fallbacks=[CommandHandler("cancel", cancel_conversation)]
    )
    application.add_handler(save_file_conv)
    application.add_handler(section_conv)
    application.add_handler(folder_conv)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_press_router))
    print("Bot is running...")
    application.run_polling()
if __name__ == "__main__":
    main()

