# database.py

import sqlite3
from config import DB_NAME

# --- دوال المستخدمين (تبقى كما هي) ---
def add_user_if_not_exists(user_id: int, first_name: str):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        existing_user = cursor.fetchone()
        if not existing_user:
            cursor.execute("INSERT INTO users (user_id, first_name) VALUES (?, ?)", (user_id, first_name))
            conn.commit()
            print(f"تمت إضافة مستخدم جديد: {first_name} ({user_id})")
        else:
            print(f"المستخدم {first_name} ({user_id}) موجود بالفعل.")
    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات: {e}")
    finally:
        if conn:
            conn.close()

# --- دوال الأقسام (تعديلات جوهرية هنا) ---

# #[تعديل]: أصبحت الدالة الآن تقبل parent_section_id اختياري
def add_section(user_id: int, section_name: str, parent_section_id: int = None):
    """
    تضيف قسمًا جديدًا. إذا تم توفير parent_section_id، يتم إنشاؤه كقسم فرعي.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sections (user_id, section_name, parent_section_id) VALUES (?, ?, ?)",
            (user_id, section_name, parent_section_id)
        )
        conn.commit()
        if parent_section_id:
            print(f"تمت إضافة قسم فرعي '{section_name}' للمستخدم {user_id}.")
        else:
            print(f"تمت إضافة قسم رئيسي '{section_name}' للمستخدم {user_id}.")
    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات عند إضافة قسم: {e}")
    finally:
        if conn:
            conn.close()

# #[إضافة جديدة]: دالة لجلب الأقسام الرئيسية فقط
def get_root_sections(user_id: int):
    """
    تجلب الأقسام الرئيسية فقط (التي ليس لها أب) لمستخدم معين.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # الشرط parent_section_id IS NULL هو ما يحدد أنها أقسام رئيسية
        cursor.execute(
            "SELECT section_id, section_name FROM sections WHERE user_id = ? AND parent_section_id IS NULL",
            (user_id,)
        )
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات عند جلب الأقسام الرئيسية: {e}")
        return []
    finally:
        if conn:
            conn.close()

# #[إضافة جديدة]: دالة لجلب الأقسام الفرعية
def get_subsections(parent_section_id: int):
    """
    تجلب كل الأقسام الفرعية التابعة مباشرة لقسم أب معين.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT section_id, section_name FROM sections WHERE parent_section_id = ?",
            (parent_section_id,)
        )
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات عند جلب الأقسام الفرعية: {e}")
        return []
    finally:
        if conn:
            conn.close()

# --- دوال المجلدات (تعديل بسيط ودالة جديدة) ---

def add_folder(owner_user_id: int, folder_name: str, section_id: int = None):
    # ... (هذه الدالة تبقى كما هي تمامًا) ...
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO folders (owner_user_id, folder_name, section_id) VALUES (?, ?, ?)",
                       (owner_user_id, folder_name, section_id))
        conn.commit()
        if section_id:
            print(f"تمت إضافة مجلد '{folder_name}' للمستخدم {owner_user_id} داخل القسم {section_id}.")
        else:
            print(f"تمت إضافة مجلد رئيسي '{folder_name}' للمستخدم {owner_user_id}.")
    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات عند إضافة مجلد: {e}")
    finally:
        if conn:
            conn.close()


def get_root_folders(user_id: int):
    """
    تجلب كل المجلدات الرئيسية (التي لا تنتمي لقسم) الخاصة بمستخدم معين.
    """
    # #[تعديل بسيط]: تم تغيير اسم الدالة من get_user_root_folders إلى get_root_folders للاتساق
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT folder_id, folder_name FROM folders WHERE owner_user_id = ? AND section_id IS NULL",
            (user_id,)
        )
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات عند جلب المجلدات الرئيسية: {e}")
        return []
    finally:
        if conn:
            conn.close()
            
# #[إضافة جديدة]: دالة لجلب المجلدات داخل قسم
def get_folders_in_section(section_id: int):
    """
    تجلب كل المجلدات الموجودة داخل قسم معين.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT folder_id, folder_name FROM folders WHERE section_id = ?",
            (section_id,)
        )
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات عند جلب المجلدات داخل قسم: {e}")
        return []
    finally:
        if conn:
            conn.close()

# --- دوال الملفات (تبقى كما هي) ---

def add_file(folder_id: int, file_unique_id: str, file_id: str, file_name: str, file_type: str, caption: str | None):
    """ #[تعديل]: أصبحت الدالة الآن تستقبل وتحفظ caption """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO files (folder_id, file_unique_id, file_id, file_name, file_type, caption) VALUES (?, ?, ?, ?, ?, ?)",
            (folder_id, file_unique_id, file_id, file_name, file_type, caption)
        )
        conn.commit()
    # ... (بقية الدالة كما هي)
    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات عند إضافة ملف: {e}")
    finally:
        if conn:
            conn.close()

def get_files_paginated(folder_id: int, limit: int, offset: int):
    """ #[تعديل]: أصبحت الدالة الآن تجلب caption أيضًا """
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM files WHERE folder_id = ?", (folder_id,))
        total_files = cursor.fetchone()[0]
        cursor.execute(
            "SELECT file_id, file_name, file_type, caption FROM files WHERE folder_id = ? LIMIT ? OFFSET ?",
            (folder_id, limit, offset)
        )
        files_page = cursor.fetchall()
        return files_page, total_files
    # ... (بقية الدالة كما هي)
    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات عند جلب الملفات المقسمة: {e}")
        return [], 0
    finally:
        if conn:
            conn.close()


def get_all_user_folders(user_id: int):
    """
    تجلب كل مجلدات المستخدم مع أسماء الأقسام التي تنتمي إليها (إن وجدت).
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                f.folder_id, 
                f.folder_name, 
                s.section_name 
            FROM 
                folders f
            LEFT JOIN 
                sections s ON f.section_id = s.section_id
            WHERE 
                f.owner_user_id = ?
        """, (user_id,))
        
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات عند جلب كل المجلدات: {e}")
        return []
    finally:
        if conn:
            conn.close()