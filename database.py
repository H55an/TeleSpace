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

# --- دوال الحاويات (الموحدة) ---

def add_container(owner_user_id: int, name: str, type: str, parent_id: int = None) -> int:
    """
    [موحد] يضيف حاوية جديدة (قسم أو مجلد) إلى قاعدة البيانات.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO containers (owner_user_id, name, type, parent_id) VALUES (?, ?, ?, ?)",
            (owner_user_id, name, type, parent_id)
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"DB Error in add_container: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_container_details(container_id: int):
    """
    [موحد] يجلب تفاصيل حاوية معينة (قسم أو مجلد).
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM containers WHERE id = ?", (container_id,))
        return cursor.fetchone()
    except sqlite3.Error as e:
        print(f"DB Error in get_container_details: {e}")
        return None
    finally:
        if conn:
            conn.close()

def rename_container(container_id: int, new_name: str):
    """
    [موحد] يعيد تسمية حاوية (قسم أو مجلد).
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE containers SET name = ? WHERE id = ?", (new_name, container_id))
        conn.commit()
    except sqlite3.Error as e:
        print(f"DB Error in rename_container: {e}")
    finally:
        if conn:
            conn.close()

def get_root_containers(user_id: int):
    """
    [موحد] يجلب الحاويات الجذرية للمستخدم (التي يملكها أو المشاركة معه).
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = """
            -- الحاويات التي يملكها المستخدم في المستوى الجذر
            SELECT id, name, owner_user_id, type
            FROM containers
            WHERE owner_user_id = :user_id AND parent_id IS NULL

            UNION

            -- الحاويات التي تمت مشاركتها مع المستخدم مباشرة
            SELECT c.id, c.name, c.owner_user_id, c.type
            FROM containers c
            JOIN permissions p ON c.id = p.content_id
            WHERE p.user_id = :user_id AND c.parent_id IS NULL -- نضمن أنها جذرية
        """
        cursor.execute(query, {'user_id': user_id})
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"DB Error in get_root_containers: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_child_containers(parent_id: int):
    """
    [موحد] يجلب كل الحاويات الفرعية (أقسام ومجلدات) لحاوية معينة.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = """
            SELECT id, name, owner_user_id, type
            FROM containers
            WHERE parent_id = ?
        """
        cursor.execute(query, (parent_id,))
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"DB Error in get_child_containers: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_container_path(container_id: int) -> list:
    """
    [موحد] يجلب مسار الحاوية على شكل قائمة من (id, name).
    """
    path = []
    current_id = container_id
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        while current_id:
            cursor.execute("SELECT id, name, parent_id FROM containers WHERE id = ?", (current_id,))
            container = cursor.fetchone()
            if container:
                path.insert(0, (container['id'], container['name']))
                current_id = container['parent_id']
            else:
                break
        return path
    except sqlite3.Error as e:
        print(f"DB Error in get_container_path: {e}")
        return []
    finally:
        if conn:
            conn.close()

def delete_container_recursively(container_id: int):
    """
    [موحد] يحذف حاوية وكل محتوياتها بشكل متكرر.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # أولاً، ابحث عن كل الحاويات الفرعية
        cursor.execute("SELECT id FROM containers WHERE parent_id = ?", (container_id,))
        child_containers = cursor.fetchall()
        for child in child_containers:
            delete_container_recursively(child[0]) # استدعاء متكرر

        # ثانياً، إذا كانت الحاوية مجلدًا، احذف العناصر بداخلها
        container_details = get_container_details(container_id)
        if container_details and container_details['type'] == 'folder':
            cursor.execute("DELETE FROM items WHERE container_id = ?", (container_id,))

        # ثالثاً، احذف الصلاحيات والمشاركات المرتبطة
        cursor.execute("DELETE FROM permissions WHERE content_id = ? AND (content_type = 'section' OR content_type = 'folder')", (container_id,))
        cursor.execute("DELETE FROM shares WHERE content_id = ? AND (content_type = 'section' OR content_type = 'folder')", (container_id,))

        # أخيراً، احذف الحاوية نفسها
        cursor.execute("DELETE FROM containers WHERE id = ?", (container_id,))
        
        conn.commit()
        print(f"تم حذف الحاوية {container_id} وكل محتوياتها بنجاح.")
    except sqlite3.Error as e:
        print(f"DB Error in delete_container_recursively: {e}")
    finally:
        if conn:
            conn.close()

def get_parent_container_id(container_id: int) -> int | None:
    """
    [موحد] يجلب معرّف الحاوية الأب.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT parent_id FROM containers WHERE id = ?", (container_id,))
        result = cursor.fetchone()
        return result[0] if result and result[0] is not None else None
    except sqlite3.Error as e:
        print(f"DB Error in get_parent_container_id: {e}")
        return None
    finally:
        if conn:
            conn.close()

# --- دوال العناصر ---

def add_item(container_id: int, item_name: str, item_type: str, content: str, file_unique_id: str = None, file_id: str = None):
    """
    [معدل] يضيف عنصر (ملف أو نص) إلى حاوية.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO items (container_id, item_name, item_type, content, file_unique_id, file_id) VALUES (?, ?, ?, ?, ?, ?)",
            (container_id, item_name, item_type, content, file_unique_id, file_id)
        )
        conn.commit()
    except sqlite3.Error as e:
        print(f"DB Error in add_item: {e}")
    finally:
        if conn:
            conn.close()

def get_items_paginated(container_id: int, limit: int, offset: int):
    """
    [معدل] يجلب العناصر من حاوية (مجلد) لإرسالها.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM items WHERE container_id = ?", (container_id,))
        total_items = cursor.fetchone()[0]
        cursor.execute(
            "SELECT item_record_id, item_name, item_type, content, file_id FROM items WHERE container_id = ? ORDER BY item_record_id ASC LIMIT ? OFFSET ?",
            (container_id, limit, offset)
        )
        items_page = cursor.fetchall()
        return items_page, total_items
    except sqlite3.Error as e:
        print(f"DB Error in get_items_paginated: {e}")
        return [], 0
    finally:
        if conn:
            conn.close()

def get_all_user_containers_for_move(user_id: int):
    """
    [جديد] يجلب كل حاويات المستخدم (أقسام ومجلدات) لغرض عرضها في قائمة النقل.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, type, parent_id
            FROM containers
            WHERE owner_user_id = ?
            ORDER BY type, name
        """, (user_id,))
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"DB Error in get_all_user_containers_for_move: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_item_details(item_record_id: int):
    """
    [بدون تغيير] يجلب تفاصيل عنصر معين.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM items WHERE item_record_id = ?", (item_record_id,))
        return cursor.fetchone()
    except sqlite3.Error as e:
        print(f"DB Error in get_item_details: {e}")
        return None
    finally:
        if conn:
            conn.close()

def delete_item(item_record_id: int):
    """
    [بدون تغيير] يحذف عنصر معين.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM items WHERE item_record_id = ?", (item_record_id,))
        conn.commit()
    except sqlite3.Error as e:
        print(f"DB Error in delete_item: {e}")
    finally:
        if conn:
            conn.close()

def delete_all_items_in_container(container_id: int):
    """
    [معدل] يحذف كل العناصر داخل حاوية (مجلد).
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM items WHERE container_id = ?", (container_id,))
        conn.commit()
        return cursor.rowcount
    except sqlite3.Error as e:
        print(f"DB Error in delete_all_items_in_container: {e}")
        return 0
    finally:
        if conn:
            conn.close()

# --- دوال المشاركة والصلاحيات ---

def get_or_create_viewer_share_link(owner_user_id: int, content_type: str, content_id: int) -> str:
    """
    [بدون تغيير] يجلب أو ينشئ رابط مشاهدة دائم.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT share_token FROM shares WHERE content_type = ? AND content_id = ? AND link_type = 'viewer'",
            (content_type, content_id)
        )
        existing_link = cursor.fetchone()
        if existing_link:
            return existing_link[0]
        else:
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
    """
    [بدون تغيير] تنشئ رابط مشاركة فريد وتخزنه.
    """
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
    """
    [بدون تغيير] تجلب تفاصيل المشاركة عبر الرمز.
    """
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
    """
    [بدون تغيير] تعطل رابط مشاركة (خاص بالمدراء) بعد استخدامه.
    """
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

def grant_permission(user_id: int, content_type: str, content_id: int, new_permission_level: str):
    """
    [بدون تغيير] تمنح أو ترقي صلاحية مستخدم على عنصر.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT permission_level FROM permissions WHERE user_id = ? AND content_type = ? AND content_id = ?",
            (user_id, content_type, content_id)
        )
        result = cursor.fetchone()
        if result:
            if new_permission_level == 'admin' and result[0] == 'viewer':
                cursor.execute(
                    "UPDATE permissions SET permission_level = ? WHERE user_id = ? AND content_type = ? AND content_id = ?",
                    (new_permission_level, user_id, content_type, content_id)
                )
        else:
            cursor.execute(
                "INSERT INTO permissions (user_id, content_type, content_id, permission_level) VALUES (?, ?, ?, ?)",
                (user_id, content_type, content_id, new_permission_level)
            )
        conn.commit()
    except sqlite3.Error as e:
        print(f"DB Error in grant_permission: {e}")
    finally:
        if conn:
            conn.close()

def revoke_permission(user_id: int, content_type: str, content_id: int):
    """
    [جديد] يلغي صلاحية مستخدم على حاوية.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM permissions WHERE user_id = ? AND content_type = ? AND content_id = ?",
            (user_id, content_type, content_id)
        )
        conn.commit()
    except sqlite3.Error as e:
        print(f"DB Error in revoke_permission: {e}")
    finally:
        if conn:
            conn.close()

def get_permission_level(user_id: int, content_type: str, content_id: int) -> str | None:
    """
    [معدل] يتحقق من مستوى صلاحية المستخدم على حاوية بشكل هرمي.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. التحقق من الملكية
        cursor.execute("SELECT owner_user_id FROM containers WHERE id = ?", (content_id,))
        owner_result = cursor.fetchone()
        if owner_result and owner_result['owner_user_id'] == user_id:
            return 'owner'

        # 2. البحث عن الصلاحيات بشكل هرمي
        current_id = content_id
        while current_id is not None:
            # ابحث عن صلاحية مباشرة على الحاوية الحالية
            # ملاحظة: content_type في جدول الصلاحيات لا يزال مهما للتمييز
            cursor.execute("""
                SELECT permission_level FROM permissions
                WHERE user_id = ? AND content_id = ?
            """, (user_id, current_id))
            permission_result = cursor.fetchone()

            if permission_result:
                return permission_result['permission_level']

            # انتقل إلى الحاوية الأب
            cursor.execute("SELECT parent_id FROM containers WHERE id = ?", (current_id,))
            parent_result = cursor.fetchone()
            current_id = parent_result['parent_id'] if parent_result else None

        return None
    except sqlite3.Error as e:
        print(f"DB Error in get_permission_level: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_back_navigation(user_id: int, container_id: int) -> str:
    """
    [معدل] يحدد زر العودة الصحيح بناءً على صلاحيات المستخدم.
    """
    details = get_container_details(container_id)
    if not details: return "my_space"

    is_owner = details['owner_user_id'] == user_id
    parent_id = details['parent_id']

    if parent_id:
        # هذه حاوية فرعية
        if is_owner:
            return f"container:{parent_id}"
        else:
            # مستخدم غير مالك، تحقق من صلاحيته على الأب
            parent_permission = get_permission_level(user_id, 'section', parent_id) # الأب دائما قسم
            if parent_permission:
                return f"container:{parent_id}"
            else:
                return "shared_spaces" # لا يملك صلاحية على الأب
    else:
        # هذه حاوية جذرية
        if is_owner:
            return "my_space"
        else:
            return "shared_spaces"

def get_shared_containers_for_user(user_id: int):
    """
    [جديد] يجلب كل الحاويات (أقسام ومجلدات) التي تمت مشاركتها مع مستخدم.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # هذا الاستعلام يجمع كل الصلاحيات المباشرة الممنوحة للمستخدم
        query = """
            SELECT c.id, c.name, c.type, c.owner_user_id, p.permission_level
            FROM containers c
            JOIN permissions p ON c.id = p.content_id
            WHERE p.user_id = :user_id
        """
        cursor.execute(query, {'user_id': user_id})
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"DB Error in get_shared_containers_for_user: {e}")
        return []
    finally:
        if conn:
            conn.close()