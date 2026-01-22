# migrate_legacy.py
# Migration of old data

import asyncio
import random  # مكتبة للعشوائية
from telegram import Bot
from telegram.error import RetryAfter, BadRequest, TimedOut, NetworkError
import psycopg2
from app.shared import config  # ملف الإعدادات

# --- إعدادات الأمان ---
BATCH_SIZE = 10              # قللنا العدد قليلاً ليكون أخف
MIN_DELAY_MSG = 2            # أقل وقت انتظار بين الرسائل (ثواني)
MAX_DELAY_MSG = 6            # أقصى وقت انتظار بين الرسائل (ثواني)
MIN_DELAY_BATCH = 40         # أقل وقت استراحة بين الدفعات (ثواني)
MAX_DELAY_BATCH = 90         # أقصى وقت استراحة بين الدفعات (ثواني)

TARGET_CHANNEL_ID = config.STORAGE_CHANNEL_ID

async def migrate_legacy_files():
    # 1. الاتصال بقاعدة البيانات
    try:
        conn = psycopg2.connect(config.DATABASE_URL)
        cursor = conn.cursor()
    except Exception as e:
        print(f"❌ فشل الاتصال بقاعدة البيانات: {e}")
        return

    # 2. تهيئة البوت
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    
    print("🚀 بدء عملية ترحيل الملفات بنظام (الوضع الآمن)...")

    while True:
        # الاستعلام عن دفعة جديدة
        try:
            query = """
                SELECT item_record_id, file_id, item_type
                FROM items 
                WHERE item_record_id NOT IN (SELECT item_id FROM file_locations)
                AND file_id IS NOT NULL
                LIMIT %s
            """
            cursor.execute(query, (BATCH_SIZE,))
            rows = cursor.fetchall()
        except Exception as e:
            print(f"❌ خطأ في قاعدة البيانات: {e}")
            await asyncio.sleep(10) # انتظار قبل المحاولة مرة أخرى
            continue

        # شرط الخروج: إذا لم تعد هناك ملفات، توقف
        if not rows:
            print("✅ تم الانتهاء! جميع الملفات تم ترحيلها بنجاح.")
            break
            
        print(f"\n📦 جاري معالجة دفعة جديدة ({len(rows)} ملف)...")

        for item_id, legacy_file_id, item_type in rows:
            try:
                sent_message = None
                
                # إرسال الملف (مع محاولة التعرف على النوع)
                # استخدام send_document كحل عام لأغلب الأنواع إذا لم يكن محدداً بدقة
                if item_type == 'photo':
                    sent_message = await bot.send_photo(chat_id=TARGET_CHANNEL_ID, photo=legacy_file_id, disable_notification=True)
                elif item_type == 'video':
                    sent_message = await bot.send_video(chat_id=TARGET_CHANNEL_ID, video=legacy_file_id, disable_notification=True)
                elif item_type == 'audio':
                    sent_message = await bot.send_audio(chat_id=TARGET_CHANNEL_ID, audio=legacy_file_id, disable_notification=True)
                elif item_type == 'voice':
                    sent_message = await bot.send_voice(chat_id=TARGET_CHANNEL_ID, voice=legacy_file_id, disable_notification=True)
                else:
                    sent_message = await bot.send_document(chat_id=TARGET_CHANNEL_ID, document=legacy_file_id, disable_notification=True)

                # الحفظ في قاعدة البيانات
                if sent_message:
                    cursor.execute("""
                        INSERT INTO file_locations (item_id, channel_id, message_id)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (channel_id, message_id) DO NOTHING
                    """, (item_id, TARGET_CHANNEL_ID, sent_message.message_id))
                    
                    conn.commit()
                    print(f"   ✓ تم ({item_id}) -> Msg: {sent_message.message_id}")
                
                # --- [1] تأخير عشوائي بين كل رسالة والأخرى ---
                # هذا يمنع البوت من الإرسال السريع جداً (Machine-gun effect)
                sleep_time = random.uniform(MIN_DELAY_MSG, MAX_DELAY_MSG)
                await asyncio.sleep(sleep_time)

            except RetryAfter as e:
                print(f"⚠️ FloodWait: طلب التيليجرام التوقف لمدة {e.retry_after} ثانية.")
                await asyncio.sleep(e.retry_after + 5) # نزيد 5 ثواني للاحتياط
            
            except (TimedOut, NetworkError):
                print("⚠️ مشكلة في الشبكة، انتظار 5 ثواني...")
                await asyncio.sleep(5)

            except BadRequest as e:
                print(f"❌ ملف تالف أو معرف غير صالح ({item_id}): {e}")
                # نقوم بوضع علامة عليه في قاعدة البيانات أو تجاهله حتى لا يعلق السكربت عليه
                # هنا سنقوم بحذفه من القائمة الحالية (تجاوزه) فقط
                pass
            
            except Exception as e:
                print(f"❌ خطأ غير متوقع في الملف {item_id}: {e}")

        # --- [2] استراحة طويلة بين الدفعات ---
        # بعد الانتهاء من الـ 20 ملف، يأخذ البوت "قيلولة"
        # هذا يوحي للسيرفر أن النشاط بشري وليس متواصلاً
        batch_sleep = random.randint(MIN_DELAY_BATCH, MAX_DELAY_BATCH)
        print(f"☕ استراحة بين الدفعات لمدة {batch_sleep} ثانية...")
        await asyncio.sleep(batch_sleep)

    cursor.close()
    conn.close()

if __name__ == "__main__":
    try:
        asyncio.run(migrate_legacy_files())
    except KeyboardInterrupt:
        print("\n🛑 تم إيقاف السكربت يدوياً.")