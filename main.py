# main.py

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    ContextTypes, 
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters
)

import config
from database import (
    add_user_if_not_exists, 
    get_user_sections, 
    get_user_root_folders,
    add_section,
    add_folder
)

AWAITING_SECTION_NAME, AWAITING_FOLDER_NAME, AWAITING_FOLDER_LOCATION = range(3)

# --- الدوال الوسيطة ---
async def forward_file_to_storage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str | None:
    # ... (هذه الدالة تبقى كما هي تمامًا) ...
    try:
        forwarded_message = await update.message.forward(chat_id=config.STORAGE_CHANNEL_ID)
        file = forwarded_message.document or forwarded_message.video or forwarded_message.photo[-1] or forwarded_message.audio
        if file:
            return file.file_unique_id
    except Exception as e:
        print(f"حدث خطأ أثناء إعادة توجيه الملف: {e}")
        return None
    return None

# --- #[تعديل هنا 1]: إنشاء دالة المعالج الفعلية ---
async def file_received_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    هذه الدالة هي التي سيتم استدعاؤها عند استلام أي ملف.
    """
    print("تم استلام ملف من المستخدم...")
    
    # الخطوة 1: إعادة توجيه الملف إلى القناة
    unique_id = await forward_file_to_storage(update, context)
    
    if unique_id:
        print(f"تمت إعادة توجيه الملف بنجاح. Unique ID: {unique_id}")
        # هنا سنبدأ محادثة حفظ الملف في المهمة القادمة
        await update.message.reply_text("تم استلام الملف بنجاح! سيتم الآن تحديد مكان الحفظ.")
    else:
        await update.message.reply_text("عذرًا، حدث خطأ أثناء معالجة الملف. يرجى المحاولة مرة أخرى.")

# ... (بقية دوال البوت مثل start و build_main_menu_keyboard ومحادثات الإنشاء تبقى كما هي) ...
# ... (لا تقم بحذف أي شيء من هنا) ...
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    add_user_if_not_exists(user_id=user.id, first_name=user.first_name)
    keyboard = await build_main_menu_keyboard(user.id)
    reply_text = f"أهلاً بك يا {user.mention_html()}! أنا بوت TeleSpace."
    if update.message:
        await update.message.reply_html(reply_text, reply_markup=keyboard)
    elif update.callback_query:
        await update.callback_query.message.edit_text(reply_text, reply_markup=keyboard, parse_mode='HTML')

async def build_main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    keyboard_layout = []
    sections = get_user_sections(user_id)
    root_folders = get_user_root_folders(user_id)
    if sections:
        section_buttons = [InlineKeyboardButton(f"📂 {s['section_name']}", callback_data=f"section:{s['section_id']}") for s in sections]
        keyboard_layout.append(section_buttons)
    if root_folders:
        folder_buttons = [InlineKeyboardButton(f"📁 {f['folder_name']}", callback_data=f"folder:{f['folder_id']}") for f in root_folders]
        keyboard_layout.append(folder_buttons)
    control_buttons = [
        InlineKeyboardButton("➕ قسم جديد", callback_data="new_section"),
        InlineKeyboardButton("➕ مجلد جديد", callback_data="new_folder")
    ]
    keyboard_layout.append(control_buttons)
    return InlineKeyboardMarkup(keyboard_layout)

async def new_section_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text="يرجى إرسال اسم القسم الجديد:")
    return AWAITING_SECTION_NAME

async def receive_section_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    section_name = update.message.text
    add_section(user_id=user.id, section_name=section_name)
    await update.message.reply_text(f"✅ تم إنشاء قسم '{section_name}' بنجاح!")
    await start(update, context)
    return ConversationHandler.END

async def new_folder_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    keyboard = []
    keyboard.append([InlineKeyboardButton("🔝 في القائمة الرئيسية", callback_data="folder_loc_root")])
    sections = get_user_sections(user_id)
    for section in sections:
        keyboard.append([InlineKeyboardButton(f"📂 داخل قسم: {section['section_name']}", callback_data=f"folder_loc_sec:{section['section_id']}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="أين تريد إنشاء المجلد الجديد؟", reply_markup=reply_markup)
    return AWAITING_FOLDER_LOCATION

async def folder_location_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    location_data = query.data
    if location_data == "folder_loc_root":
        context.user_data['selected_section_id'] = None
        await query.edit_message_text(text="اخترت القائمة الرئيسية. الآن، أرسل اسم المجلد الجديد:")
    else:
        section_id = int(location_data.split(':')[1])
        context.user_data['selected_section_id'] = section_id
        await query.edit_message_text(text="اخترت القسم. الآن، أرسل اسم المجلد الجديد:")
    return AWAITING_FOLDER_NAME

async def receive_folder_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    folder_name = update.message.text
    section_id = context.user_data.get('selected_section_id')
    add_folder(owner_user_id=user.id, folder_name=folder_name, section_id=section_id)
    await update.message.reply_text(f"✅ تم إنشاء مجلد '{folder_name}' بنجاح!")
    context.user_data.clear()
    await start(update, context)
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("تم إلغاء العملية.")
    await start(update, context)
    return ConversationHandler.END


def main() -> None:
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # --- #[تعديل هنا 2]: استبدال None باسم الدالة الجديدة ---
    file_handler = MessageHandler(
        filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO,
        file_received_handler
    )
    # --------------------------------------------------------

    new_section_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_section_start, pattern="^new_section$")],
        states={AWAITING_SECTION_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_section_name)]},
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    new_folder_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_folder_start, pattern="^new_folder$")],
        states={
            AWAITING_FOLDER_LOCATION: [CallbackQueryHandler(folder_location_received, pattern="^folder_loc_")],
            AWAITING_FOLDER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_folder_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    application.add_handler(file_handler)
    application.add_handler(new_section_conv_handler)
    application.add_handler(new_folder_conv_handler)
    application.add_handler(CommandHandler("start", start))
    
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()