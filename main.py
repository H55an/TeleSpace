# main.py

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters
)

import config
# #[تعديل 1]: تحديث قائمة الاستيراد بالكامل
from database import (
    add_user_if_not_exists,
    add_section, get_root_sections, get_subsections,
    add_folder, get_root_folders, get_folders_in_section,
    add_file, get_files_paginated
)

# --- تعريف حالات المحادثة ---
(AWAITING_SECTION_NAME, AWAITING_FOLDER_NAME) = range(2)

# --- الدوال المساعدة ---
async def send_files_paginated(update: Update, context: ContextTypes.DEFAULT_TYPE, folder_id: int, offset: int = 0):
    # ... (هذه الدالة تبقى كما هي تمامًا) ...
    query = update.callback_query
    chat_id = update.effective_chat.id
    PAGE_SIZE = 10
    files_page, total_files = get_files_paginated(folder_id, limit=PAGE_SIZE, offset=offset)
    if not files_page:
        await context.bot.send_message(chat_id, "لا توجد ملفات أخرى لعرضها.")
        return
    await context.bot.send_message(chat_id, f"إرسال {len(files_page)} ملفات (من {offset + 1} إلى {offset + len(files_page)})...")
    for file in files_page:
        try:
            await context.bot.send_document(chat_id=chat_id, document=file['file_id'])
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

# --- دوال الواجهة الرئيسية والتصفح ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ يعالج أمر /start ويعرض الواجهة الرئيسية. """
    user = update.effective_user
    add_user_if_not_exists(user_id=user.id, first_name=user.first_name)
    
    keyboard = build_main_menu_keyboard(user.id)
    reply_text = "🗂️ **الواجهة الرئيسية**\n\nاختر قسمًا أو مجلدًا للتصفح."
    
    # نستخدم نفس المنطق لتحديث الرسالة أو إرسال واحدة جديدة
    if update.message:
        await update.message.reply_html(reply_text, reply_markup=keyboard)
    elif update.callback_query:
        try:
            await update.callback_query.message.edit_text(reply_text, reply_markup=keyboard, parse_mode='HTML')
        except Exception: # في حالة عدم تغير الرسالة، نتجنب الخطأ
            pass
            
    return ConversationHandler.END

def build_main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """ #[تعديل 2]: تبني لوحة الأزرار للواجهة الرئيسية (الأقسام والمجلدات الرئيسية فقط). """
    keyboard_layout = []
    
    # جلب الأقسام الرئيسية فقط
    root_sections = get_root_sections(user_id)
    if root_sections:
        section_buttons = [InlineKeyboardButton(f"📂 {s['section_name']}", callback_data=f"section:{s['section_id']}") for s in root_sections]
        keyboard_layout.append(section_buttons)
        
    # جلب المجلدات الرئيسية فقط
    root_folders = get_root_folders(user_id)
    if root_folders:
        folder_buttons = [InlineKeyboardButton(f"📁 {f['folder_name']}", callback_data=f"folder:{f['folder_id']}") for f in root_folders]
        keyboard_layout.append(folder_buttons)
        
    control_buttons = [
        InlineKeyboardButton("➕ قسم رئيسي", callback_data="new_section_root"),
        InlineKeyboardButton("➕ مجلد رئيسي", callback_data="new_folder_root")
    ]
    keyboard_layout.append(control_buttons)
    
    return InlineKeyboardMarkup(keyboard_layout)

# --- #[تعديل 3]: الموجه المركزي الجديد بالكامل ---
async def button_press_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ يستقبل ويوجه كل نقرات الأزرار الخاصة بالتصفح. """
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    
    # الحالة 1: عرض محتويات قسم (أقسام فرعية ومجلدات)
    if data.startswith("section:"):
        section_id = int(data.split(':')[1])
        
        keyboard_layout = []
        subsections = get_subsections(section_id)
        if subsections:
            subsection_buttons = [InlineKeyboardButton(f"📂 {s['section_name']}", callback_data=f"section:{s['section_id']}") for s in subsections]
            keyboard_layout.append(subsection_buttons)

        folders_in_section = get_folders_in_section(section_id)
        if folders_in_section:
            folder_buttons = [InlineKeyboardButton(f"📁 {f['folder_name']}", callback_data=f"folder:{f['folder_id']}") for f in folders_in_section]
            keyboard_layout.append(folder_buttons)
            
        # إضافة أزرار التحكم الخاصة بالقسم الحالي
        control_buttons = [
            InlineKeyboardButton("➕ قسم فرعي هنا", callback_data=f"new_section_sub:{section_id}"),
            InlineKeyboardButton("➕ مجلد جديد هنا", callback_data=f"new_folder_in_sec:{section_id}")
        ]
        keyboard_layout.append(control_buttons)
        keyboard_layout.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")])
        
        reply_markup = InlineKeyboardMarkup(keyboard_layout)
        await query.message.edit_text("اختر قسمًا فرعيًا أو مجلدًا:", reply_markup=reply_markup)

    # الحالة 2: بدء إرسال ملفات مجلد
    elif data.startswith("folder:"):
        folder_id = int(data.split(':')[1])
        await query.delete_message()
        await send_files_paginated(update, context, folder_id, offset=0)

    # الحالة 3: طلب الدفعة التالية من الملفات
    elif data.startswith("next_files:"):
        _, folder_id, offset = data.split(':')
        await query.delete_message()
        await send_files_paginated(update, context, int(folder_id), int(offset))

    # الحالة 4: العودة للقائمة الرئيسية
    elif data == "back_to_main":
        await start(update, context)


# --- #[تعديل 4]: محادثة إنشاء الأقسام (أصبحت أذكى) ---
async def new_section_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ يسأل المستخدم عن اسم القسم الجديد ويخزن موقع الأب مؤقتًا. """
    query = update.callback_query
    await query.answer()
    data = query.data

    parent_id = None
    if data.startswith("new_section_sub:"):
        parent_id = int(data.split(':')[1])
    
    # نخزن ID الأب في الذاكرة المؤقتة للمحادثة
    context.user_data['parent_section_id'] = parent_id
    
    await query.message.edit_text(text="يرجى إرسال اسم القسم الجديد:")
    return AWAITING_SECTION_NAME

async def receive_section_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ يستقبل الاسم وينشئ القسم في الموقع الصحيح. """
    user = update.effective_user
    section_name = update.message.text
    parent_id = context.user_data.get('parent_section_id')
    
    add_section(user_id=user.id, section_name=section_name, parent_section_id=parent_id)
    
    await update.message.reply_text(f"✅ تم إنشاء قسم '{section_name}' بنجاح!")
    context.user_data.clear()
    await start(update, context)
    return ConversationHandler.END


# --- (بقية الكود: محادثات إنشاء المجلدات وحفظ الملفات تبقى كما هي الآن) ---
# ... (Please copy the rest of the functions from the previous response here:
# new_folder_start, folder_location_received, receive_folder_name,
# file_received_handler, save_file_to_location, cancel_conversation)
# Note: We will need to update new_folder_start in a future step, but for now it's okay.
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("تم إلغاء العملية.")
    await start(update, context)
    return ConversationHandler.END

# --- نقطة انطلاق البوت ---
def main() -> None:
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # #[تعديل 5]: تحديث معالج محادثة إنشاء الأقسام
    section_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(new_section_prompt, pattern="^new_section_root$"),
            CallbackQueryHandler(new_section_prompt, pattern="^new_section_sub:")
        ],
        states={
            AWAITING_SECTION_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_section_name)]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation), CommandHandler("start", start)]
    )

    # ... (بقية معالجات المحادثات تبقى كما هي الآن) ...
    # ... (We will update the new_folder conversation handler next) ...
    
    application.add_handler(section_conv)
    # ... (Add other handlers here)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_press_router))
    
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()