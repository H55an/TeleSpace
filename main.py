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
    add_folder # #[إضافة جديدة]: استيراد دالة إضافة المجلد
)

# --- تعريف حالات المحادثة ---
# #[إضافة جديدة]: أضفنا حالة جديدة لاختيار موقع المجلد
AWAITING_SECTION_NAME, AWAITING_FOLDER_NAME, AWAITING_FOLDER_LOCATION = range(3)

# --- الدوال الأساسية (تبقى كما هي) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (هذه الدالة تبقى كما هي تمامًا) ...
    user = update.effective_user
    add_user_if_not_exists(user_id=user.id, first_name=user.first_name)
    keyboard = await build_main_menu_keyboard(user.id)
    reply_text = f"أهلاً بك يا {user.mention_html()}! أنا بوت TeleSpace."
    if update.message:
        await update.message.reply_html(reply_text, reply_markup=keyboard)
    elif update.callback_query:
        await update.callback_query.message.edit_text(reply_text, reply_markup=keyboard, parse_mode='HTML')

async def build_main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    # ... (هذه الدالة تبقى كما هي تمامًا) ...
    keyboard_layout = []
    sections = get_user_sections(user_id)
    root_folders = get_user_root_folders(user_id)
    if sections:
        section_buttons = [InlineKeyboardButton(f"🗂️{s['section_name']}", callback_data=f"section:{s['section_id']}") for s in sections]
        keyboard_layout.append(section_buttons)
    if root_folders:
        folder_buttons = [InlineKeyboardButton(f"📁{f['folder_name']}", callback_data=f"folder:{f['folder_id']}") for f in root_folders]
        keyboard_layout.append(folder_buttons)
    control_buttons = [
        InlineKeyboardButton("➕ قسم جديد", callback_data="new_section"),
        InlineKeyboardButton("➕ مجلد جديد", callback_data="new_folder")
    ]
    keyboard_layout.append(control_buttons)
    return InlineKeyboardMarkup(keyboard_layout)

# --- دوال محادثة إنشاء قسم (تبقى كما هي) ---
async def new_section_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ... (هذه الدالة تبقى كما هي تمامًا) ...
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text="يرجى إرسال اسم القسم الجديد:")
    return AWAITING_SECTION_NAME

async def receive_section_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ... (هذه الدالة تبقى كما هي تمامًا) ...
    user = update.effective_user
    section_name = update.message.text
    add_section(user_id=user.id, section_name=section_name)
    await update.message.reply_text(f"✅ تم إنشاء قسم '{section_name}' بنجاح!")
    await start(update, context)
    return ConversationHandler.END

# --- #[إضافة جديدة]: دوال محادثة إنشاء مجلد ---

async def new_folder_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ الخطوة الأولى في إنشاء مجلد: سؤال المستخدم عن الموقع. """
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    # بناء لوحة أزرار لاختيار الموقع
    keyboard = []
    # إضافة زر لإنشاء المجلد في القائمة الرئيسية
    keyboard.append([InlineKeyboardButton("🔝في القائمة الرئيسية", callback_data="folder_loc_root")])
    
    # إضافة أزرار لكل قسم موجود
    sections = get_user_sections(user_id)
    for section in sections:
        keyboard.append([InlineKeyboardButton(f"📂داخل قسم: {section['section_name']}", callback_data=f"folder_loc_sec:{section['section_id']}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="أين تريد إنشاء المجلد الجديد؟", reply_markup=reply_markup)
    
    return AWAITING_FOLDER_LOCATION

async def folder_location_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ الخطوة الثانية: استلام الموقع وتخزينه، ثم طلب اسم المجلد. """
    query = update.callback_query
    await query.answer()
    
    # callback_data ستكون إما 'folder_loc_root' أو 'folder_loc_sec:123'
    location_data = query.data
    
    if location_data == "folder_loc_root":
        # نخزن في الذاكرة المؤقتة أن المستخدم اختار القائمة الرئيسية
        context.user_data['selected_section_id'] = None
        await query.edit_message_text(text="اخترت القائمة الرئيسية. الآن، أرسل اسم المجلد الجديد:")
    else:
        # نستخرج رقم القسم من callback_data
        section_id = int(location_data.split(':')[1])
        # نخزن رقم القسم المختار في الذاكرة المؤقتة
        context.user_data['selected_section_id'] = section_id
        await query.edit_message_text(text="اخترت القسم. الآن، أرسل اسم المجلد الجديد:")
        
    return AWAITING_FOLDER_NAME

async def receive_folder_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ الخطوة الثالثة والأخيرة: استلام الاسم وإنشاء المجلد. """
    user = update.effective_user
    folder_name = update.message.text
    
    # نسترجع الموقع الذي تم اختياره من الذاكرة المؤقتة
    section_id = context.user_data.get('selected_section_id')
    
    # نستخدم دالة قاعدة البيانات لإنشاء المجلد
    add_folder(owner_user_id=user.id, folder_name=folder_name, section_id=section_id)
    
    await update.message.reply_text(f"✅ تم إنشاء مجلد '{folder_name}' بنجاح!")
    
    # ننظف الذاكرة المؤقتة بعد الاستخدام
    context.user_data.clear()
    
    await start(update, context) # نعود للقائمة الرئيسية المحدثة
    return ConversationHandler.END


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ... (هذه الدالة تبقى كما هي تمامًا) ...
    await update.message.reply_text("تم إلغاء العملية.")
    await start(update, context)
    return ConversationHandler.END


def main() -> None:
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # معالج محادثة إنشاء قسم (يبقى كما هو)
    new_section_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_section_start, pattern="^new_section$")],
        states={AWAITING_SECTION_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_section_name)]},
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    # #[إضافة جديدة]: معالج محادثة إنشاء مجلد
    new_folder_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_folder_start, pattern="^new_folder$")],
        states={
            AWAITING_FOLDER_LOCATION: [CallbackQueryHandler(folder_location_received, pattern="^folder_loc_")],
            AWAITING_FOLDER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_folder_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    application.add_handler(new_section_conv_handler)
    application.add_handler(new_folder_conv_handler) # #[إضافة جديدة]: تسجيل المعالج الجديد
    application.add_handler(CommandHandler("start", start))
    
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()