# database_setup.py

import sqlite3

# اسم ملف قاعدة البيانات الذي سيتم إنشاؤه
DB_NAME = "telespace.db"

def setup_database():
    """
    هذه الدالة تقوم بالاتصال بقاعدة البيانات، وإنشاء الجداول إذا لم تكن موجودة.
    """
    # 1. الاتصال بقاعدة البيانات
    conn = sqlite3.connect(DB_NAME)

    # 2. إنشاء "مؤشر" (Cursor)
    cursor = conn.cursor()

    # --- جدول المستخدمين ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT NOT NULL
    )
    """)

    # --- جدول الحاويات (الموحد للأقسام والمجلدات) ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS containers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        type TEXT NOT NULL, -- 'section' or 'folder'
        parent_id INTEGER,
        FOREIGN KEY (owner_user_id) REFERENCES users (user_id),
        FOREIGN KEY (parent_id) REFERENCES containers (id)
    )
    """)
    
    # --- جدول العناصر (الملفات والرسائل) ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items (
        item_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
        container_id INTEGER NOT NULL, -- تم التغيير من folder_id
        file_unique_id TEXT,
        file_id TEXT,
        item_name TEXT,
        item_type TEXT NOT NULL,
        content TEXT,
        FOREIGN KEY (container_id) REFERENCES containers (id) -- تم تحديث الربط
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
        content_type TEXT NOT NULL, -- 'section' or 'folder'
        content_id INTEGER NOT NULL,
        permission_level TEXT NOT NULL, -- 'viewer' or 'admin'
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    """)

    # 4. حفظ التغييرات وإغلاق الاتصال
    conn.commit()
    conn.close()

    print("قاعدة البيانات والجداول تم تحديثها بنجاح!")

# نقطة انطلاق السكربت
if __name__ == "__main__":
    setup_database()
