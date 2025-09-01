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

def add_item(folder_id: int, item_name: str, item_type: str, content: str, file_unique_id: str = None, file_id: str = None):
    """ يضيف أي عنصر (ملف أو نص) إلى قاعدة البيانات. """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO items (folder_id, item_name, item_type, content, file_unique_id, file_id) VALUES (?, ?, ?, ?, ?, ?)",
            (folder_id, item_name, item_type, content, file_unique_id, file_id)
        )
        conn.commit()
    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات عند إضافة عنصر: {e}")
    finally:
        if conn:
            conn.close()

def get_items_paginated(folder_id: int, limit: int, offset: int):
    """ يجلب العناصر من مجلد لإرسالها. """
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM items WHERE folder_id = ?", (folder_id,))
        total_items = cursor.fetchone()[0]
        # #[تعديل هنا]: نتأكد من جلب item_record_id
        cursor.execute(
            "SELECT item_record_id, item_name, item_type, content, file_id FROM items WHERE folder_id = ? ORDER BY item_record_id ASC LIMIT ? OFFSET ?",
            (folder_id, limit, offset)
        )
        items_page = cursor.fetchall()
        return items_page, total_items
    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات عند جلب العناصر المقسمة: {e}")
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


def get_item_details(item_record_id: int):
    """
    تجلب تفاصيل عنصر معين باستخدام معرّفه الفريد في قاعدة البيانات.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # نستخدم * لجلب كل الأعمدة لهذا العنصر
        cursor.execute("SELECT * FROM items WHERE item_record_id = ?", (item_record_id,))
        return cursor.fetchone()
    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات عند جلب تفاصيل العنصر: {e}")
        return None
    finally:
        if conn:
            conn.close()

def delete_item(item_record_id: int):
    """
    تقوم بحذف عنصر معين من جدول items.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM items WHERE item_record_id = ?", (item_record_id,))
        conn.commit()
        print(f"تم حذف العنصر برقم {item_record_id} بنجاح.")
    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات عند حذف العنصر: {e}")
    finally:
        if conn:
            conn.close()


def delete_all_items_in_folder(folder_id: int):
    """
    تقوم بحذف كل العناصر الموجودة داخل مجلد معين.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM items WHERE folder_id = ?", (folder_id,))
        conn.commit()
        # نرجع عدد الصفوف التي تم حذفها
        return cursor.rowcount
    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات عند حذف كل العناصر: {e}")
        return 0
    finally:
        if conn:
            conn.close()


def delete_folder(folder_id: int):
    """
    تقوم بحذف مجلد وكل العناصر الموجودة بداخله.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # الخطوة 1: حذف كل العناصر داخل المجلد
        cursor.execute("DELETE FROM items WHERE folder_id = ?", (folder_id,))
        print(f"تم حذف {cursor.rowcount} عنصر من المجلد {folder_id}.")
        
        # الخطوة 2: حذف المجلد نفسه
        cursor.execute("DELETE FROM folders WHERE folder_id = ?", (folder_id,))
        print(f"تم حذف المجلد {folder_id} بنجاح.")

        conn.commit()
    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات عند حذف المجلد: {e}")
    finally:
        if conn:
            conn.close()


            
def delete_section_recursively(section_id: int):
    """
    تقوم بحذف قسم وكل محتوياته (أقسام فرعية، مجلدات، عناصر) بشكل متكرر.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # الخطوة 1: ابحث عن كل الأقسام الفرعية داخل هذا القسم
        cursor.execute("SELECT section_id FROM sections WHERE parent_section_id = ?", (section_id,))
        subsections = cursor.fetchall()
        for sub in subsections:
            # استدعاء الدالة لنفسها لحذف كل قسم فرعي ومحتوياته
            delete_section_recursively(sub[0])
            
        # الخطوة 2: ابحث عن كل المجلدات داخل هذا القسم
        cursor.execute("SELECT folder_id FROM folders WHERE section_id = ?", (section_id,))
        folders = cursor.fetchall()
        for folder in folders:
            # استخدم دالة حذف المجلدات الموجودة لدينا
            delete_folder(folder[0])

        # الخطوة 3: بعد حذف كل المحتويات، احذف القسم نفسه
        cursor.execute("DELETE FROM sections WHERE section_id = ?", (section_id,))
        
        conn.commit()
        print(f"تم حذف القسم {section_id} وكل محتوياته بنجاح.")
    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات عند حذف القسم بشكل متكرر: {e}")
    finally:
        if conn:
            conn.close()