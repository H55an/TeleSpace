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
    نقطة انطلاق البوت.
    """
    # 1. إنشاء التطبيق
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # 2. إعداد وتسجيل المعالجات (Handlers)
    # معالج محادثة إنشاء قسم
    section_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handlers.new_section_prompt, pattern="^new_section_root$"),
            CallbackQueryHandler(handlers.new_section_prompt, pattern="^new_section_sub:")
        ],
        states={AWAITING_SECTION_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.receive_section_name)]},
        fallbacks=[CommandHandler("cancel", handlers.cancel_conversation)]
    )

    # معالج محادثة إنشاء مجلد
    folder_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handlers.new_folder_prompt, pattern="^new_folder_root$"),
            CallbackQueryHandler(handlers.new_folder_prompt, pattern="^new_folder_in_sec:")
        ],
        states={AWAITING_FOLDER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.receive_folder_name)]},
        fallbacks=[CommandHandler("cancel", handlers.cancel_conversation)]
    )

    # معالج محادثة حفظ الملفات
    save_file_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO, handlers.file_received_handler)],
        states={AWAITING_SAVE_LOCATION: [CallbackQueryHandler(handlers.save_location_selected, pattern="^save_to_folder:")]},
        fallbacks=[CommandHandler("cancel", handlers.cancel_conversation), CommandHandler("start", handlers.start)],
    )

    # تسجيل كل المعالجات في التطبيق
    application.add_handler(section_conv)
    application.add_handler(folder_conv)
    application.add_handler(save_file_conv)
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CallbackQueryHandler(handlers.button_press_router))
    
    # 3. تشغيل البوت
    # هذه الدالة وحدها ستقوم بكل شيء: التجهيز، التشغيل، والاستماع، والإيقاف الآمن
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()