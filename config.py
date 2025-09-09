# config.py
import os
from dotenv import load_dotenv

# يقوم بتحميل المتغيرات من ملف .env (هذا للتشغيل المحلي فقط)
load_dotenv()

# جلب توكن البوت من متغيرات البيئة
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# جلب رابط قاعدة البيانات من متغيرات البيئة
DATABASE_URL = os.getenv("DATABASE_URL")

# جلب بقية الإعدادات
STORAGE_CHANNEL_ID = int(os.getenv("STORAGE_CHANNEL_ID"))
DB_NAME = "telespace_db" # هذا لن نستخدمه في الاستضافة، لكن يمكن إبقاؤه

# تأكد من أن المتغيرات الأساسية موجودة
if not TELEGRAM_BOT_TOKEN or not DATABASE_URL:
    raise ValueError("Missing critical environment variables: TELEGRAM_BOT_TOKEN or DATABASE_URL")