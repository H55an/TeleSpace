# main.py

# 1. استيراد المكتبات اللازمة
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# 2. استيراد التوكن من ملف الإعدادات
import config

# 3. تعريف دالة أمر /start
#    هذه الدالة سيتم استدعاؤها في كل مرة يرسل فيها المستخدم أمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # update: يحتوي على كل المعلومات الواردة من المستخدم (من هو، ما هي الرسالة، إلخ)
    # context: كائن يمكن استخدامه لتمرير معلومات إضافية داخل البوت (لن نستخدمه الآن)
    
    user = update.effective_user
    # نحصل على معلومات المستخدم الذي أرسل الأمر للترحيب به باسمه
    
    # نرسل رسالة ترحيبية كرد على المستخدم
    await update.message.reply_html(
        f"أهلاً بك يا {user.mention_html()}! أنا بوت TeleSpace، مساعدك لتنظيم ملفاتك.",
    )

# 4. تعريف الدالة الرئيسية لتشغيل البوت
def main() -> None:
    # إنشاء كائن "التطبيق" وربطه بتوكن البوت الخاص بنا
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # تسجيل معالج الأوامر: نخبر التطبيق أنه عندما يتلقى أمرًا اسمه "start"
    # يجب عليه استدعاء الدالة التي اسمها start
    application.add_handler(CommandHandler("start", start))

    # طباعة رسالة في الطرفية لتأكيد أن البوت يعمل
    print("Bot is running...")

    # تشغيل البوت: سيبدأ البوت في الاستماع بشكل مستمر لأي رسائل جديدة من تيليجرام
    application.run_polling()

# 5. نقطة انطلاق البرنامج
#    هذا السطر يتأكد من أن دالة main() سيتم تشغيلها فقط عندما نقوم بتشغيل هذا الملف مباشرة
if __name__ == "__main__":
    main()