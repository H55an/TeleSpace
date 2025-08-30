# database.py

import sqlite3
from config import DB_NAME # نستورد اسم قاعدة البيانات من ملف الإعدادات

def add_user_if_not_exists(user_id: int, first_name: str):
    """
    تضيف مستخدمًا جديدًا إلى جدول users إذا لم يكن موجودًا بالفعل.
    Args:
        user_id (int): معرف المستخدم الفريد من تيليجرام.
        first_name (str): الاسم الأول للمستخدم.
    """
    try:
        # نتصل بقاعدة البيانات
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # 1. التحقق من وجود المستخدم
        #    نبحث عن صف في جدول users حيث user_id يطابق المعرف الذي تم تمريره
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        
        # .fetchone() تقوم بجلب نتيجة واحدة فقط من البحث
        existing_user = cursor.fetchone()

        # 2. إضافة المستخدم إذا لم يكن موجودًا
        if not existing_user:
            # نستخدم علامات الاستفهام (?) لمنع هجمات SQL Injection
            # هذه هي الطريقة الآمنة لتمرير المتغيرات إلى أوامر SQL
            cursor.execute("INSERT INTO users (user_id, first_name) VALUES (?, ?)", 
                           (user_id, first_name))
            conn.commit() # نحفظ التغيير
            print(f"تمت إضافة مستخدم جديد: {first_name} ({user_id})")
        else:
            print(f"المستخدم {first_name} ({user_id}) موجود بالفعل.")

    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات: {e}")
    finally:
        # 3. التأكد من إغلاق الاتصال دائمًا
        if conn:
            conn.close()