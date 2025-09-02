# main.py

from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters
)

# نستورد كل الأدوات اللازمة من ملفاتنا
import config
from constants import *
import handlers

def main() -> None:
    """
    نقطة انطلاق البوت. تقوم بإنشاء التطبيق، تسجيل المعالجات، وتشغيل البوت.
    """
    # 1. إنشاء التطبيق
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # 2. إعداد وتسجيل المعالجات (Handlers)

    # معالج محادثة إنشاء قسم (يبقى كما هو)
    section_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handlers.new_section_prompt, pattern="^new_section_root$"),
            CallbackQueryHandler(handlers.new_section_prompt, pattern="^new_section_sub:")
        ],
        states={AWAITING_SECTION_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.receive_section_name)]},
        fallbacks=[CommandHandler("cancel", handlers.cancel_conversation)]
    )

    # معالج محادثة إنشاء مجلد (يبقى كما هو)
    folder_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handlers.new_folder_prompt, pattern="^new_folder_root$"),
            CallbackQueryHandler(handlers.new_folder_prompt, pattern="^new_folder_in_sec:")
        ],
        states={AWAITING_FOLDER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.receive_folder_name)]},
        fallbacks=[CommandHandler("cancel", handlers.cancel_conversation)]
    )

    # #[التغيير الرئيسي هنا]: محادثة إضافة الملفات الموجهة الجديدة
    upload_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handlers.add_files_start, pattern="^add_files_to:")],
        states={
            # في هذه الحالة، نستمع لأي نوع من الرسائل (ملفات، نصوص، صور، الخ) طالما أنها ليست أمرًا
            AWAITING_FILES_FOR_UPLOAD: [MessageHandler(filters.ALL & ~filters.COMMAND, handlers.collect_files_and_save)]
        },
        fallbacks=[CommandHandler("cancel", handlers.cancel_conversation)]
    )

    # معالج محادثة إعادة تسمية المجلد
    rename_folder_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handlers.rename_folder_prompt, pattern="^rename_folder_prompt:")],
        states={
            AWAITING_RENAME_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.receive_new_folder_name)]
        },
        fallbacks=[CommandHandler("cancel", handlers.cancel_conversation)]
    )

    # معالج محادثة إعادة تسمية القسم
    rename_section_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handlers.rename_section_prompt, pattern="^rename_section_prompt:")],
        states={
            AWAITING_RENAME_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.receive_new_section_name)]
        },
        fallbacks=[CommandHandler("cancel", handlers.cancel_conversation)]
    )

    # تسجيل كل المعالجات في التطبيق
    # يتم تسجيل المحادثات أولاً لتكون لها الأولوية في التقاط التحديثات
    application.add_handler(section_conv)
    application.add_handler(folder_conv)
    application.add_handler(upload_conv) # <-- تسجيل المحادثة الجديدة
    application.add_handler(rename_folder_conv)
    application.add_handler(rename_section_conv)
    
    # ثم يتم تسجيل الأوامر والمعالج العام للأزرار
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CallbackQueryHandler(handlers.button_press_router))
    
    # 3. تشغيل البوت
    print("Bot is running... Press Ctrl+C to stop.")
    application.run_polling()

if __name__ == "__main__":
    main()
