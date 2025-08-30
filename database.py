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


def add_section(user_id: int, section_name: str):
    """
    تضيف قسمًا جديدًا مرتبطًا بمستخدم معين.
    Args:
        user_id (int): معرف المستخدم صاحب القسم.
        section_name (str): اسم القسم الجديد.
    """
    try:
        # 1. نتصل بقاعدة البيانات
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # 2. تنفيذ أمر الإضافة (INSERT)
        #    نضيف صفًا جديدًا إلى جدول sections
        #    ونقوم بتمرير user_id و section_name كقيم
        cursor.execute("INSERT INTO sections (user_id, section_name) VALUES (?, ?)",
                       (user_id, section_name))
        
        # 3. حفظ التغيير بشكل دائم في قاعدة البيانات
        conn.commit()
        print(f"تمت إضافة قسم '{section_name}' للمستخدم {user_id} بنجاح.")

    except sqlite3.Error as e:
        # في حال حدوث أي خطأ في قاعدة البيانات، نقوم بطباعته
        print(f"حدث خطأ في قاعدة البيانات عند إضافة قسم: {e}")
    finally:
        # 4. في كل الأحوال (سواء نجحت العملية أم فشلت)، نغلق الاتصال
        if conn:
            conn.close()