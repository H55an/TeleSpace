# config.py
import os
from dotenv import load_dotenv

# يقوم بتحميل المتغيرات من ملف .env (هذا للتشغيل المحلي فقط)
load_dotenv()

# --- المتغيرات الأساسية ---
# جلب توكن البوت من متغيرات البيئة
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEVELOPER_NAME = "Hassan AL-Naqeeb"
DEVELOPER_ID = 5372240626

# جلب رابط قاعدة البيانات من متغيرات البيئة
DATABASE_URL = os.getenv("DATABASE_URL")

# [جديد] مفتاح API لـ OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


# --- إعدادات القنوات ---
# معرف القناة التي يتم فيها تخزين الملفات (للحفظ الآمن)
STORAGE_CHANNEL_ID = -1003046683134

# [مطلوب] إعدادات بوابة التحقق (يجب تعديلها)
# ضع هنا معرف القناة الرقمي الذي يجب على المستخدمين الاشتراك بها
# مثال: -1001234567890
REQUIRED_CHANNEL_ID = -1003093025900

# ضع هنا رابط الدعوة الخاص بقناتك
# مثال: "https://t.me/your_channel_name"
REQUIRED_CHANNEL_LINK = "https://t.me/TeleSpace_0"


# --- التحقق من المتغيرات ---
# تأكد من أن المتغيرات الأساسية موجودة
if not TELEGRAM_BOT_TOKEN or not DATABASE_URL:
    raise ValueError("Missing critical environment variables: TELEGRAM_BOT_TOKEN or DATABASE_URL")

if REQUIRED_CHANNEL_ID == "PLEASE_UPDATE_ME" or REQUIRED_CHANNEL_LINK == "PLEASE_UPDATE_ME":
    print("Warning: REQUIRED_CHANNEL_ID and REQUIRED_CHANNEL_LINK are not set in config.py or .env file. The subscription feature will not work correctly.")