# main.py

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters
)

import config
# نتأكد من استيراد كل الدوال التي نستخدمها بالفعل
from database import (
    add_user_if_not_exists,
    add_section, get_root_sections, get_subsections,
    add_folder, get_root_folders, get_folders_in_section,
    add_file, get_files_paginated
)

# --- تعريف حالات المحادثة ---
# نحتاج فقط حالتين الآن: واحدة لاسم القسم، وواحدة لاسم المجلد
(AWAITING_SECTION_NAME, AWAITING_FOLDER_NAME) = range(2)

# --- الدوال المساعدة ---
async def send_files_paginated(update: Update, context: ContextTypes.DEFAULT_TYPE, folder_id: int, offset: int = 0):
    """
    تجلب وترسل دفعة من الملفات من مجلد معين.
    """
    query = update.callback_query
    chat_id = update.effective_chat.id
    PAGE_SIZE = 10 
    
    files_page, total_files = get_files_paginated(folder_id, limit=PAGE_SIZE, offset=offset)

    if not files_page and offset == 0:
        # إذا كان المجلد فارغًا من البداية
        await context.bot.send_message(chat_id, "هذا المجلد فارغ.")
        # نعود للمستخدم إلى القائمة الرئيسية بعد إعلامه
        await start(update, context)
        return

    if not files_page:
        await context.bot.send_message(chat_id, "لا توجد ملفات أخرى لعرضها.")
        return

    await context.bot.send_message(chat_id, f"إرسال {len(files_page)} ملفات (من {offset + 1} إلى {offset + total_files})...")
    for file in files_page:
        try:
            # نستخدم send_document كإجراء افتراضي، يمكن تحسينه لاحقًا ليدعم كل الأنواع
            await context.bot.send_document(chat_id=chat_id, document=file['file_id'])
            await asyncio.sleep(0.5) 
        except Exception as e:
            await context.bot.send_message(chat_id, f"لم يتم إرسال الملف '{file['file_name']}'. الخطأ: {e}")

    new_offset = offset + PAGE_SIZE
    if new_offset < total_files:
        keyboard = [[
            InlineKeyboardButton(f"📥 إرسال الـ {min(PAGE_SIZE, total_files - new_offset)} ملفات التالية", 
                                 callback_data=f"next_files:{folder_id}:{new_offset}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id, "لا يزال هناك المزيد من الملفات.", reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id, "تم إرسال كل الملفات في هذا المجلد.")

# --- دوال الواجهة الرئيسية والتصفح ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ يعالج أمر /start ويعرض الواجهة الرئيسية. """
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
    """ تبني لوحة الأزرار للواجهة الرئيسية (الأقسام والمجلدات الرئيسية فقط). """
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
    """ يستقبل ويوجه كل نقرات الأزرار الخاصة بالتصفح. """
    query = update.callback_query
    await query.answer()
    data = query.data
    
    # عرض محتويات قسم
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
        # زر العودة للوراء (سيتم برمجته لاحقًا) وزر العودة للرئيسية
        keyboard_layout.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")])
        
        reply_markup = InlineKeyboardMarkup(keyboard_layout)
        await query.message.edit_text("اختر قسمًا فرعيًا أو مجلدًا:", reply_markup=reply_markup)

    # بدء إرسال ملفات مجلد
    elif data.startswith("folder:"):
        folder_id = int(data.split(':')[1])
        await query.delete_message()
        await send_files_paginated(update, context, folder_id, offset=0)

    # طلب الدفعة التالية من الملفات
    elif data.startswith("next_files:"):
        _, folder_id, offset = data.split(':')
        await query.delete_message()
        await send_files_paginated(update, context, int(folder_id), int(offset))

    # العودة للقائمة الرئيسية
    elif data == "back_to_main":
        await start(update, context)

# --- محادثة إنشاء قسم ---
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

# --- محادثة إنشاء مجلد ---
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

# --- محادثة حفظ الملفات (سيتم برمجتها لاحقًا) ---
async def file_received_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This will be implemented in a future task.
    # For now, we just acknowledge receipt.
    await update.message.reply_text("تم استلام الملف! ميزة الحفظ قيد التطوير.")


# --- دالة الإلغاء العامة ---
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("تم إلغاء العملية.")
    await start(update, context)
    return ConversationHandler.END

# --- نقطة انطلاق البوت ---
def main() -> None:
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # معالج محادثة إنشاء قسم
    section_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(new_section_prompt, pattern="^new_section_root$"),
            CallbackQueryHandler(new_section_prompt, pattern="^new_section_sub:")
        ],
        states={AWAITING_SECTION_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_section_name)]},
        fallbacks=[CommandHandler("cancel", cancel_conversation)]
    )

    # معالج محادثة إنشاء مجلد
    folder_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(new_folder_prompt, pattern="^new_folder_root$"),
            CallbackQueryHandler(new_folder_prompt, pattern="^new_folder_in_sec:")
        ],
        states={AWAITING_FOLDER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_folder_name)]},
        fallbacks=[CommandHandler("cancel", cancel_conversation)]
    )

    # معالج استلام الملفات (مؤقت، سيتم تحويله لمحادثة لاحقًا)
    file_handler = MessageHandler(filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO, file_received_handler)

    # تسجيل المعالجات
    application.add_handler(section_conv)
    application.add_handler(folder_conv)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(file_handler) # معالج الملفات
    application.add_handler(CallbackQueryHandler(button_press_router)) # الموجه يجب أن يكون أخيرًا
    
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
