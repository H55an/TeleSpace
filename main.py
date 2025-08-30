# main.py

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters
)

import config
from database import (
    add_user_if_not_exists, get_user_sections, get_user_root_folders,
    add_section, add_folder, get_all_user_folders, # #[إضافة جديدة]: استيراد الدالة الجديدة
    add_file 
)

# --- تعريف حالات المحادثة ---
# #[إضافة جديدة]: أضفنا حالة جديدة لانتظار اختيار موقع الحفظ
(AWAITING_SECTION_NAME, AWAITING_FOLDER_NAME, AWAITING_FOLDER_LOCATION,
 AWAITING_SAVE_LOCATION) = range(4)

# --- دوال البوت ---

async def forward_file_to_storage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> dict | None:
    # #[تعديل]: الآن الدالة تعيد قاموسًا بمعلومات الملف وليس فقط unique_id
    try:
        message = update.message
        forwarded_message = await message.forward(chat_id=config.STORAGE_CHANNEL_ID)
        
        file = (forwarded_message.document or forwarded_message.video or 
                forwarded_message.photo[-1] or forwarded_message.audio)

        if file:
            return {
                'file_unique_id': file.file_unique_id,
                'file_id': file.file_id,
                'file_name': getattr(file, 'file_name', 'اسم غير متوفر') # الحصول على الاسم إن وجد
            }
    except Exception as e:
        print(f"حدث خطأ أثناء إعادة توجيه الملف: {e}")
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ... (هذه الدالة تبقى كما هي) ...
    user = update.effective_user
    add_user_if_not_exists(user_id=user.id, first_name=user.first_name)
    keyboard = await build_main_menu_keyboard(user.id)
    reply_text = f"أهلاً بك يا {user.mention_html()}! أنا بوت TeleSpace."
    if update.message:
        await update.message.reply_html(reply_text, reply_markup=keyboard)
    elif update.callback_query:
        await update.callback_query.message.edit_text(reply_text, reply_markup=keyboard, parse_mode='HTML')
    # #[إضافة جديدة]: إنهاء أي محادثة قد تكون عالقة
    return ConversationHandler.END


async def build_main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    # ... (هذه الدالة تبقى كما هي) ...
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

# --- محادثات الإنشاء (تبقى كما هي) ---
# ... (كل دوال محادثات إنشاء القسم والمجلد تبقى هنا دون تغيير) ...
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
    keyboard = [[InlineKeyboardButton("🔝 في القائمة الرئيسية", callback_data="folder_loc_root")]]
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

# --- #[إضافة جديدة]: دوال محادثة حفظ الملف ---

async def file_received_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ نقطة الدخول لمحادثة الحفظ. يتم تفعيلها عند استلام ملف. """
    user_id = update.effective_user.id
    file_info = await forward_file_to_storage(update, context)
    
    if not file_info:
        await update.message.reply_text("عذرًا، حدث خطأ أثناء معالجة الملف.")
        return ConversationHandler.END

    # نخزن معلومات الملف مؤقتًا في ذاكرة المستخدم
    context.user_data['file_to_save'] = file_info
    
    # بناء لوحة أزرار بكل المجلدات المتاحة
    keyboard = []
    all_folders = get_all_user_folders(user_id)
    
    if not all_folders:
        await update.message.reply_text("ليس لديك أي مجلدات بعد. يرجى إنشاء مجلد أولاً باستخدام /start.")
        return ConversationHandler.END

    for folder in all_folders:
        # نعرض اسم القسم بجانب اسم المجلد ليكون واضحًا
        display_name = f"📁 {folder['folder_name']}"
        if folder['section_name']:
            display_name += f" (قسم: {folder['section_name']})"
            
        keyboard.append([
            InlineKeyboardButton(display_name, callback_data=f"save_to_folder:{folder['folder_id']}")
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("تم استلام الملف. أين تريد حفظه؟", reply_markup=reply_markup)
    
    return AWAITING_SAVE_LOCATION

async def save_file_to_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ يتم تفعيلها عند الضغط على زر مجلد لحفظ الملف. """
    query = update.callback_query
    await query.answer()

    folder_id = int(query.data.split(':')[1])
    file_info = context.user_data.get('file_to_save')

    if not file_info:
        await query.edit_message_text("عذرًا، يبدو أن معلومات الملف قد ضاعت. يرجى المحاولة مرة أخرى.")
        return ConversationHandler.END

   # نستدعي دالة قاعدة البيانات ونمرر لها المعلومات التي جمعناها
    add_file(
        folder_id=folder_id,
        file_unique_id=file_info['file_unique_id'],
        file_id=file_info['file_id'],
        file_name=file_info['file_name']
    )
    # ---------------------------------------------
    
    await query.edit_message_text(f"✅ تم حفظ الملف بنجاح!")
    context.user_data.clear() # ننظف الذاكرة المؤقتة
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("تم إلغاء العملية.")
    await start(update, context) # نعود للقائمة الرئيسية
    return ConversationHandler.END


def main() -> None:
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # #[إضافة جديدة]: محادثة حفظ الملفات
    save_file_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO, file_received_handler)
        ],
        states={
            AWAITING_SAVE_LOCATION: [CallbackQueryHandler(save_file_to_location, pattern="^save_to_folder:")]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation), CommandHandler("start", start)],
    )

    # ... (بقية معالجات المحادثات تبقى كما هي) ...
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

    # تسجيل المعالجات بالترتيب الصحيح (المحادثات أولاً)
    application.add_handler(save_file_conv_handler)
    application.add_handler(new_section_conv_handler)
    application.add_handler(new_folder_conv_handler)
    application.add_handler(CommandHandler("start", start))
    
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()