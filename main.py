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
    [معدل] نقطة انطلاق البوت مع المعالجات الموحدة.
    """
    # 1. إنشاء التطبيق
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # 2. إعداد وتسجيل المعالجات (Handlers)

    # معالج محادثة موحد لإنشاء الحاويات (أقسام ومجلدات)
    create_container_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handlers.new_container_prompt, pattern="^new_container_root:"),
            CallbackQueryHandler(handlers.new_container_prompt, pattern="^new_container_sub:")
        ],
        states={AWAITING_CONTAINER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.receive_container_name)]},
        fallbacks=[CommandHandler("cancel", handlers.cancel_conversation), CommandHandler("info", handlers.info), CommandHandler("start", handlers.start)]
    )

    # معالج محادثة موحد لإعادة تسمية الحاويات
    rename_container_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handlers.rename_container_prompt, pattern="^rename_container:")],
        states={AWAITING_RENAME_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.receive_new_container_name)]},
        fallbacks=[CommandHandler("cancel", handlers.cancel_conversation), CommandHandler("info", handlers.info), CommandHandler("start", handlers.start)]
    )

    # معالج محادثة إضافة العناصر إلى مجلد
    add_items_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handlers.add_items_start, pattern="^add_items:")],
        states={
            AWAITING_ITEMS_FOR_UPLOAD: [
                CommandHandler("done", handlers.save_items),
                MessageHandler(filters.ALL & ~filters.COMMAND, handlers.collect_items)
            ]
        },
        fallbacks=[CommandHandler("cancel", handlers.cancel_conversation), CommandHandler("info", handlers.info), CommandHandler("start", handlers.start)]
    )

    # تسجيل كل المعالجات في التطبيق
    application.add_handler(create_container_conv)
    application.add_handler(rename_container_conv)
    application.add_handler(add_items_conv)
    
    # ثم يتم تسجيل الأوامر والمعالج العام للأزرار
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("info", handlers.info))
    application.add_handler(CallbackQueryHandler(handlers.button_press_router))
    
    # 3. تشغيل البوت
    print("Bot is running... Press Ctrl+C to stop.")
    application.run_polling()

if __name__ == "__main__":
    main()