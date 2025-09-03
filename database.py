# database.py

import sqlite3
import uuid
from config import DB_NAME

# --- دوال المستخدمين ---
def add_user_if_not_exists(user_id: int, first_name: str):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO users (user_id, first_name) VALUES (?, ?)", (user_id, first_name))
            conn.commit()
    except sqlite3.Error as e:
        print(f"DB Error in add_user_if_not_exists: {e}")
    finally:
        if conn:
            conn.close()

# --- دوال الأقسام ---
def add_section(user_id: int, section_name: str, parent_section_id: int = None):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sections (user_id, section_name, parent_section_id) VALUES (?, ?, ?)",
            (user_id, section_name, parent_section_id)
        )
        conn.commit()
    except sqlite3.Error as e:
        print(f"DB Error in add_section: {e}")
    finally:
        if conn:
            conn.close()

def get_root_sections(user_id: int):
    """[تعديل]: تجلب الأقسام الرئيسية التي يملكها المستخدم أو لديه صلاحية عليها."""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = """
            SELECT s.section_id, s.section_name, s.user_id as owner_user_id
            FROM sections s
            LEFT JOIN permissions p ON s.section_id = p.content_id AND p.content_type = 'section'
            WHERE (s.user_id = :user_id OR p.user_id = :user_id) AND s.parent_section_id IS NULL
            GROUP BY s.section_id
        """
        cursor.execute(query, {'user_id': user_id})
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"DB Error in get_root_sections: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_subsections(parent_section_id: int):
    """[تعديل]: تجلب كل الأقسام الفرعية لقسم معين، بغض النظر عن الصلاحيات."""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = """
            SELECT section_id, section_name, user_id as owner_user_id
            FROM sections
            WHERE parent_section_id = ?
        """
        cursor.execute(query, (parent_section_id,))
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"DB Error in get_subsections: {e}")
        return []
    finally:
        if conn:
            conn.close()
# --- دوال المجلدات (تعديل بسيط ودالة جديدة) ---

def add_folder(owner_user_id: int, folder_name: str, section_id: int = None):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO folders (owner_user_id, folder_name, section_id) VALUES (?, ?, ?)",
                       (owner_user_id, folder_name, section_id))
        conn.commit()
    except sqlite3.Error as e:
        print(f"DB Error in add_folder: {e}")
    finally:
        if conn:
            conn.close()



def get_root_folders(user_id: int):
    """[تعديل]: تجلب المجلدات الرئيسية التي يملكها المستخدم أو لديه صلاحية عليها."""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = """
            SELECT f.folder_id, f.folder_name, f.owner_user_id
            FROM folders f
            LEFT JOIN permissions p ON f.folder_id = p.content_id AND p.content_type = 'folder'
            WHERE (f.owner_user_id = :user_id OR p.user_id = :user_id) AND f.section_id IS NULL
            GROUP BY f.folder_id
        """
        cursor.execute(query, {'user_id': user_id})
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"DB Error in get_root_folders: {e}")
        return []
    finally:
        if conn:
            conn.close()
            
# #[إضافة جديدة]: دالة لجلب المجلدات داخل قسم
def get_folders_in_section(section_id: int):
    """[تعديل]: تجلب كل المجلدات داخل قسم معين، بغض النظر عن الصلاحيات."""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = """
            SELECT folder_id, folder_name, owner_user_id
            FROM folders
            WHERE section_id = ?
        """
        cursor.execute(query, (section_id,))
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"DB Error in get_folders_in_section: {e}")
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

def get_folder_details(folder_id: int):
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM folders WHERE folder_id = ?", (folder_id,))
        return cursor.fetchone()
    except sqlite3.Error as e:
        print(f"DB Error in get_folder_details: {e}")
        return None
    finally:
        if conn:
            conn.close()

def rename_folder(folder_id: int, new_name: str):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE folders SET folder_name = ? WHERE folder_id = ?", (new_name, folder_id))
        conn.commit()
    except sqlite3.Error as e:
        print(f"DB Error in rename_folder: {e}")
    finally:
        if conn:
            conn.close()

def get_section_details(section_id: int):
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sections WHERE section_id = ?", (section_id,))
        return cursor.fetchone()
    except sqlite3.Error as e:
        print(f"DB Error in get_section_details: {e}")
        return None
    finally:
        if conn:
            conn.close()

def rename_section(section_id: int, new_name: str):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE sections SET section_name = ? WHERE section_id = ?", (new_name, section_id))
        conn.commit()
    except sqlite3.Error as e:
        print(f"DB Error in rename_section: {e}")
    finally:
        if conn:
            conn.close()

# --- دوال المشاركة والصلاحيات ---
def get_or_create_viewer_share_link(owner_user_id: int, content_type: str, content_id: int) -> str:
    """
    [جديد] يجلب رابط مشاهدة دائم موجود أو ينشئ واحدًا جديدًا إذا لم يكن موجودًا.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # ابحث عن رابط مشاهدة موجود
        cursor.execute(
            "SELECT share_token FROM shares WHERE content_type = ? AND content_id = ? AND link_type = 'viewer'",
            (content_type, content_id)
        )
        existing_link = cursor.fetchone()

        if existing_link:
            return existing_link[0]  # أعد التوكن الموجود
        else:
            # إذا لم يكن هناك رابط، أنشئ واحدًا جديدًا
            token = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO shares (share_token, content_type, content_id, owner_user_id, link_type) VALUES (?, ?, ?, ?, ?)",
                (token, content_type, content_id, owner_user_id, 'viewer')
            )
            conn.commit()
            return token

    except sqlite3.Error as e:
        print(f"DB Error in get_or_create_viewer_share_link: {e}")
        return None
    finally:
        if conn:
            conn.close()


def create_share_link(owner_user_id: int, content_type: str, content_id: int, link_type: str) -> str:
    """تنشئ رابط مشاركة فريد وتخزنه."""
    token = str(uuid.uuid4())
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO shares (share_token, content_type, content_id, owner_user_id, link_type) VALUES (?, ?, ?, ?, ?)",
            (token, content_type, content_id, owner_user_id, link_type)
        )
        conn.commit()
        return token
    except sqlite3.Error as e:
        print(f"DB Error in create_share_link: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_share_by_token(token: str):
    """تجلب تفاصيل المشاركة عبر الرمز."""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM shares WHERE share_token = ?", (token,))
        return cursor.fetchone()
    except sqlite3.Error as e:
        print(f"DB Error in get_share_by_token: {e}")
        return None
    finally:
        if conn:
            conn.close()

def deactivate_share_link(token: str):
    """تعطل رابط مشاركة (خاص بالمدراء) بعد استخدامه."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE shares SET is_used = 1 WHERE share_token = ?", (token,))
        conn.commit()
    except sqlite3.Error as e:
        print(f"DB Error in deactivate_share_link: {e}")
    finally:
        if conn:
            conn.close()

def grant_permission(user_id: int, content_type: str, content_id: int, permission_level: str):
    """تمنح صلاحية لمستخدم على عنصر معين."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # التأكد من عدم وجود الصلاحية مسبقًا لتجنب التكرار
        cursor.execute("SELECT permission_id FROM permissions WHERE user_id = ? AND content_type = ? AND content_id = ?", (user_id, content_type, content_id))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO permissions (user_id, content_type, content_id, permission_level) VALUES (?, ?, ?, ?)",
                (user_id, content_type, content_id, permission_level)
            )
            conn.commit()
    except sqlite3.Error as e:
        print(f"DB Error in grant_permission: {e}")
    finally:
        if conn:
            conn.close()

def get_permission_level(user_id: int, content_type: str, content_id: int) -> str | None:
    """
    [جديد] يتحقق من مستوى صلاحية المستخدم على عنصر معين بشكل هرمي.
    يعيد 'owner', 'admin', 'viewer', أو None.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. التحقق من الملكية أولاً
        owner_id_col = None
        if content_type == 'section':
            cursor.execute("SELECT user_id FROM sections WHERE section_id = ?", (content_id,))
            owner_id_col = 'user_id'
        elif content_type == 'folder':
            cursor.execute("SELECT owner_user_id FROM folders WHERE folder_id = ?", (content_id,))
            owner_id_col = 'owner_user_id'
        else:
            return None

        owner_result = cursor.fetchone()
        if owner_result and owner_result[owner_id_col] == user_id:
            return 'owner'

        # 2. البحث عن الصلاحيات بشكل هرمي (من العنصر الحالي صعودًا إلى الأصل)
        current_type = content_type
        current_id = content_id

        while current_id is not None:
            # البحث عن صلاحية مباشرة على العنصر الحالي
            cursor.execute("""
                SELECT permission_level FROM permissions
                WHERE user_id = ? AND content_type = ? AND content_id = ?
            """, (user_id, current_type, current_id))
            permission_result = cursor.fetchone()

            if permission_result:
                return permission_result['permission_level']

            # إذا لم توجد صلاحية مباشرة، انتقل إلى العنصر الأب
            if current_type == 'section':
                cursor.execute("SELECT parent_section_id FROM sections WHERE section_id = ?", (current_id,))
                parent_result = cursor.fetchone()
                current_id = parent_result['parent_section_id'] if parent_result else None
            elif current_type == 'folder':
                cursor.execute("SELECT section_id FROM folders WHERE folder_id = ?", (current_id,))
                parent_result = cursor.fetchone()
                current_id = parent_result['section_id'] if parent_result else None
                current_type = 'section'
            else:
                break

        return None

    except sqlite3.Error as e:
        print(f"DB Error in get_permission_level: {e}")
        return None
    finally:
        if conn:
            conn.close()


def revoke_permission(user_id: int, content_type: str, content_id: int):
    """
    [جديد] تزيل صلاحية مستخدم معين من على عنصر معين.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM permissions WHERE user_id = ? AND content_type = ? AND content_id = ?",
            (user_id, content_type, content_id)
        )
        conn.commit()
        print(f"Revoked permission for user {user_id} from {content_type}:{content_id}")
    except sqlite3.Error as e:
        print(f"DB Error in revoke_permission: {e}")
    finally:
        if conn:
            conn.close()