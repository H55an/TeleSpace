# database_setup.py

import sqlite3

# اسم ملف قاعدة البيانات الذي سيتم إنشاؤه
DB_NAME = "telespace.db"

def setup_database():
    """
    هذه الدالة تقوم بالاتصال بقاعدة البيانات، وإنشاء الجداول إذا لم تكن موجودة.
    """
    # 1. الاتصال بقاعدة البيانات
    #    سيقوم هذا الأمر بإنشاء ملف telespace.db إذا لم يكن موجودًا
    conn = sqlite3.connect(DB_NAME)

    # 2. إنشاء "مؤشر" (Cursor)
    #    المؤشر هو الأداة التي نستخدمها لتنفيذ أوامر SQL
    cursor = conn.cursor()

    # 3. تعريف أوامر SQL لإنشاء الجداول
    #    نستخدم علامات التنصيص الثلاثية لكتابة الأوامر على عدة أسطر لتكون واضحة
    #    PRIMARY KEY: يعني أن هذا الحقل هو المعرف الفريد لكل صف، ولا يمكن أن يتكرر
    #    NOT NULL: يعني أن هذا الحقل لا يمكن أن يكون فارغًا
    #    FOREIGN KEY: يقوم بربط جدول بجدول آخر

    # --- جدول المستخدمين ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT NOT NULL
    )
    """)

    # --- جدول الأقسام ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sections (
        section_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        section_name TEXT NOT NULL,
        parent_section_id INTEGER, 
        FOREIGN KEY (user_id) REFERENCES users (user_id),
        FOREIGN KEY (parent_section_id) REFERENCES sections (section_id)
    )
    """)

    # --- جدول المجلدات ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS folders (
        folder_id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_user_id INTEGER NOT NULL,
        folder_name TEXT NOT NULL,
        section_id INTEGER,
        FOREIGN KEY (owner_user_id) REFERENCES users (user_id),
        FOREIGN KEY (section_id) REFERENCES sections (section_id)
    )
    """)
    
    # --- جدول الملفات ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items (
    item_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_id INTEGER NOT NULL,

    -- أصبح اختياريًا (NULL للرسائل النصية)
    file_unique_id TEXT, 

    -- أصبح اختياريًا (NULL للرسائل النصية)
    file_id TEXT, 

    item_name TEXT,
    item_type TEXT NOT NULL,

    -- سيحتوي على وصف الملفات، أو النص الكامل للرسائل
    content TEXT,

    FOREIGN KEY (folder_id) REFERENCES folders (folder_id)
)
""")

    # --- جدول لرموز المشاركة ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS shares (
        share_id INTEGER PRIMARY KEY AUTOINCREMENT,
        share_token TEXT NOT NULL UNIQUE,
        content_type TEXT NOT NULL, -- 'section' or 'folder'
        content_id INTEGER NOT NULL,
        owner_user_id INTEGER NOT NULL,
        link_type TEXT NOT NULL, -- 'viewer' or 'admin'
        is_used BOOLEAN NOT NULL DEFAULT 0,
        FOREIGN KEY (owner_user_id) REFERENCES users (user_id)
    )
    """)

    # --- جدول الصلاحيات ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS permissions (
        permission_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        content_type TEXT NOT NULL,
        content_id INTEGER NOT NULL,
        permission_level TEXT NOT NULL, -- 'viewer' or 'admin'
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    """)

    # 4. حفظ التغييرات وإغلاق الاتصال
    conn.commit()  # هذا الأمر يقوم بحفظ كل التغييرات التي قمنا بها
    conn.close()   # هذا الأمر يغلق الاتصال بقاعدة البيانات

    print("قاعدة البيانات والجداول تم إنشاؤها بنجاح!")

# نقطة انطلاق السكربت
if __name__ == "__main__":
    setup_database()