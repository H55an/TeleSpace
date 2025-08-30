# main.py

import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import config
from database import add_user_if_not_exists 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    add_user_if_not_exists(user_id=user.id, first_name=user.first_name)
    
    await update.message.reply_html(
        f"أهلاً بك يا {user.mention_html()}! أنا بوت TeleSpace، مساعدك لتنظيم ملفاتك.",
    )

def main() -> None:
    """
    الدالة الرئيسية لتشغيل البوت. هذه هي الطريقة الموصى بها.
    """
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # تسجيل معالج الأوامر
    application.add_handler(CommandHandler("start", start))
    
    # طباعة رسالة في الطرفية لتأكيد أن البوت يعمل
    print("Bot is running...")
    
    # **[التغيير الوحيد والمهم]**: تشغيل البوت باستخدام run_polling
    # هذه الدالة تقوم بكل شيء: التجهيز، التشغيل، وإدارة حلقة الأحداث بنفسها.
    application.run_polling()


# نقطة انطلاق البرنامج
if __name__ == "__main__":
    main()