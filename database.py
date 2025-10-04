# database.py

import psycopg2
import psycopg2.extras
import uuid
import config

# --- Connection Helper ---
def get_db_connection():
    """
    Creates and returns a new database connection.
    """
    try:
        conn = psycopg2.connect(
            config.DATABASE_URL
        )
        return conn
    except psycopg2.Error as e:
        print(f"DB Connection Error: {e}")
        return None

# --- Activity Log Functions ---
def _log_activity(cursor, user_id: int, activity_type: str, target_id: int = None, target_type: str = None, details: str = None):
    """
    [Internal] Logs a user activity using the provided cursor.
    """
    try:
        cursor.execute(
            """
            INSERT INTO activity_log (user_id, activity_type, target_id, target_type, details)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, activity_type, target_id, target_type, details)
        )
    except psycopg2.Error as e:
        # Log the error but don't interrupt the main operation
        print(f"DB Error in _log_activity: {e}")

# --- User Functions ---
def add_user_if_not_exists(user_id: int, first_name: str):
    """
    Adds a new user if they don't exist and logs the join activity.
    Also updates the last_active_date for existing users.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return
        
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
            if cursor.fetchone():
                # User exists, just update their last active time
                cursor.execute("UPDATE users SET last_active_date = NOW() WHERE user_id = %s", (user_id,))
            else:
                # New user, insert them and log it
                cursor.execute(
                    "INSERT INTO users (user_id, first_name, join_date, last_active_date) VALUES (%s, %s, NOW(), NOW())", 
                    (user_id, first_name)
                )
                _log_activity(cursor, user_id, 'USER_JOINED')
            conn.commit()
    except psycopg2.Error as e:
        print(f"DB Error in add_user_if_not_exists: {e}")
    finally:
        if conn:
            conn.close()

def update_user_last_active(user_id: int):
    """
    Updates the last_active_date for a given user.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return
        with conn.cursor() as cursor:
            cursor.execute("UPDATE users SET last_active_date = NOW() WHERE user_id = %s", (user_id,))
            conn.commit()
    except psycopg2.Error as e:
        print(f"DB Error in update_user_last_active: {e}")
    finally:
        if conn:
            conn.close()

# --- Container Functions (Unified) ---
def add_container(owner_user_id: int, name: str, type: str, parent_id: int = None) -> int:
    """
    Adds a new container and logs the creation activity.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return None

        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO containers (owner_user_id, name, type, parent_id, creation_date) VALUES (%s, %s, %s, %s, NOW()) RETURNING id",
                (owner_user_id, name, type, parent_id)
            )
            new_id = cursor.fetchone()[0]
            _log_activity(cursor, owner_user_id, f'CREATE_{type.upper()}', new_id, type, f"Name: {name}")
            conn.commit()
            return new_id
    except psycopg2.Error as e:
        print(f"DB Error in add_container: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_container_details(container_id: int):
    """
    [Unified] Fetches details for a specific container.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return None
        
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT * FROM containers WHERE id = %s", (container_id,))
            return cursor.fetchone()
    except psycopg2.Error as e:
        print(f"DB Error in get_container_details: {e}")
        return None
    finally:
        if conn:
            conn.close()

def container_exists(container_id: int) -> bool:
    """
    Checks if a container with the given ID exists.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return False
        
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM containers WHERE id = %s", (container_id,))
            return cursor.fetchone() is not None
    except psycopg2.Error as e:
        print(f"DB Error in container_exists: {e}")
        return False
    finally:
        if conn:
            conn.close()

def rename_container(container_id: int, new_name: str, user_id: int):
    """
    Renames a container and logs the activity.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return

        with conn.cursor() as cursor:
            cursor.execute("UPDATE containers SET name = %s WHERE id = %s", (new_name, container_id))
            _log_activity(cursor, user_id, 'RENAME_CONTAINER', container_id, 'container', f"New Name: {new_name}")
            conn.commit()
    except psycopg2.Error as e:
        print(f"DB Error in rename_container: {e}")
    finally:
        if conn:
            conn.close()

def get_root_containers(user_id: int):
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return []

        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            query = """
                SELECT id, name, owner_user_id, type
                FROM containers
                WHERE owner_user_id = %(user_id)s AND parent_id IS NULL
                UNION
                SELECT c.id, c.name, c.owner_user_id, c.type
                FROM containers c
                JOIN permissions p ON c.id = p.content_id
                WHERE p.user_id = %(user_id)s AND c.parent_id IS NULL
            """
            cursor.execute(query, {'user_id': user_id})
            return cursor.fetchall()
    except psycopg2.Error as e:
        print(f"DB Error in get_root_containers: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_child_containers(parent_id: int):
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return []

        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT id, name, owner_user_id, type FROM containers WHERE parent_id = %s", (parent_id,))
            return cursor.fetchall()
    except psycopg2.Error as e:
        print(f"DB Error in get_child_containers: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_all_folders_recursively(parent_id: int) -> list:
    """[جديد] يجلب كل المجلدات (وليس الأقسام) الموجودة تحت حاوية أصل معينة بشكل متعمق."""
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return []

        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # استخدام استعلام متكرر (CTE) لاجتياز التسلسل الهرمي
            query = """
                WITH RECURSIVE container_hierarchy AS (
                    -- الجزء الأساسي: الحاويات المباشرة تحت الأصل
                    SELECT id, type
                    FROM containers
                    WHERE parent_id = %s

                    UNION ALL

                    -- الجزء المتكرر: أبناء الحاويات التي تم العثور عليها في الخطوة السابقة
                    SELECT c.id, c.type
                    FROM containers c
                    JOIN container_hierarchy ch ON c.parent_id = ch.id
                )
                -- اختيار المجلدات فقط من التسلسل الهرمي بأكمله
                SELECT c.id, c.name
                FROM containers c
                JOIN container_hierarchy ch ON c.id = ch.id
                WHERE c.type = 'folder';
            """
            cursor.execute(query, (parent_id,))
            return cursor.fetchall()
    except psycopg2.Error as e:
        print(f"DB Error in get_all_folders_recursively: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_all_containers_recursively(parent_id: int) -> list:
    """[جديد] يجلب كل الحاويات (أقسام ومجلدات) الموجودة تحت حاوية أصل معينة بشكل متعمق."""
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return []

        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # استخدام استعلام متكرر (CTE) لاجتياز التسلسل الهرمي
            query = """
                WITH RECURSIVE container_hierarchy AS (
                    -- الجزء الأساسي: الحاويات المباشرة تحت الأصل
                    SELECT id, name, type, parent_id
                    FROM containers
                    WHERE parent_id = %s

                    UNION ALL

                    -- الجزء المتكرر: أبناء الحاويات التي تم العثور عليها في الخطوة السابقة
                    SELECT c.id, c.name, c.type, c.parent_id
                    FROM containers c
                    JOIN container_hierarchy ch ON c.parent_id = ch.id
                )
                -- اختيار كل شيء من التسلسل الهرمي
                SELECT id, name, type FROM container_hierarchy;
            """
            cursor.execute(query, (parent_id,))
            return cursor.fetchall()
    except psycopg2.Error as e:
        print(f"DB Error in get_all_containers_recursively: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_container_path(container_id: int) -> list:
    path = []
    current_id = container_id
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return []

        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            while current_id:
                cursor.execute("SELECT id, name, parent_id FROM containers WHERE id = %s", (current_id,))
                container = cursor.fetchone()
                if container:
                    path.insert(0, (container['id'], container['name']))
                    current_id = container['parent_id']
                else:
                    break
        return path
    except psycopg2.Error as e:
        print(f"DB Error in get_container_path: {e}")
        return []
    finally:
        if conn:
            conn.close()

def _delete_container_recursive_step(cursor, container_id: int, user_id: int):
    """Helper for recursive deletion that also logs the activity."""
    # Fetch details before deleting for logging
    cursor.execute("SELECT name, type FROM containers WHERE id = %s", (container_id,))
    details = cursor.fetchone()
    if details:
        name, type = details
        _log_activity(cursor, user_id, f'DELETE_{type.upper()}', container_id, type, f"Name: {name}")

    # Find and delete child containers first
    cursor.execute("SELECT id FROM containers WHERE parent_id = %s", (container_id,))
    child_containers = cursor.fetchall()
    for child in child_containers:
        _delete_container_recursive_step(cursor, child[0], user_id)

    # Delete the container itself (permissions, shares, items, etc. are deleted by CASCADE)
    cursor.execute("DELETE FROM containers WHERE id = %s", (container_id,))

def delete_container_recursively(container_id: int, user_id: int):
    """
    Deletes a container and all its contents, logging the deletion.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return

        with conn.cursor() as cursor:
            _delete_container_recursive_step(cursor, container_id, user_id)
        
        conn.commit()
        print(f"Successfully deleted container {container_id} and all its contents.")
    except psycopg2.Error as e:
        if conn: conn.rollback()
        print(f"DB Error in delete_container_recursively: {e}")
    finally:
        if conn:
            conn.close()

def get_parent_container_id(container_id: int) -> int | None:
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return None

        with conn.cursor() as cursor:
            cursor.execute("SELECT parent_id FROM containers WHERE id = %s", (container_id,))
            result = cursor.fetchone()
            return result[0] if result and result[0] is not None else None
    except psycopg2.Error as e:
        print(f"DB Error in get_parent_container_id: {e}")
        return None
    finally:
        if conn:
            conn.close()

# --- Item Functions ---
def add_item(container_id: int, user_id: int, item_name: str, item_type: str, content: str, file_unique_id: str = None, file_id: str = None) -> int | None:
    """
    Adds an item to a container, logs the activity, and returns the new item's ID.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return None

        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO items (container_id, item_name, item_type, content, file_unique_id, file_id, upload_date) VALUES (%s, %s, %s, %s, %s, %s, NOW()) RETURNING item_record_id",
                (container_id, item_name, item_type, content, file_unique_id, file_id)
            )
            item_id = cursor.fetchone()[0]
            _log_activity(cursor, user_id, 'ADD_ITEM', item_id, 'item', f"Name: {item_name} in container {container_id}")
            conn.commit()
            return item_id
    except psycopg2.Error as e:
        print(f"DB Error in add_item: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_items_paginated(container_id: int, limit: int, offset: int):
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return [], 0

        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT COUNT(*) FROM items WHERE container_id = %s", (container_id,))
            total_items = cursor.fetchone()[0]
            
            cursor.execute(
                "SELECT item_record_id, item_name, item_type, content, file_id FROM items WHERE container_id = %s ORDER BY upload_date ASC, item_record_id ASC LIMIT %s OFFSET %s",
                (container_id, limit, offset)
            )
            items_page = cursor.fetchall()
            return items_page, total_items
    except psycopg2.Error as e:
        print(f"DB Error in get_items_paginated: {e}")
        return [], 0
    finally:
        if conn:
            conn.close()

def get_all_user_containers_for_move(user_id: int):
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return []

        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("""
                SELECT id, name, type, parent_id
                FROM containers
                WHERE owner_user_id = %s
                ORDER BY type, name
            """, (user_id,))
            return cursor.fetchall()
    except psycopg2.Error as e:
        print(f"DB Error in get_all_user_containers_for_move: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_item_details(item_record_id: int):
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return None

        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT * FROM items WHERE item_record_id = %s", (item_record_id,))
            return cursor.fetchone()
    except psycopg2.Error as e:
        print(f"DB Error in get_item_details: {e}")
        return None
    finally:
        if conn:
            conn.close()

def item_exists(item_record_id: int) -> bool:
    """
    Checks if an item with the given ID exists.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return False
        
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM items WHERE item_record_id = %s", (item_record_id,))
            return cursor.fetchone() is not None
    except psycopg2.Error as e:
        print(f"DB Error in item_exists: {e}")
        return False
    finally:
        if conn:
            conn.close()

def delete_item(item_record_id: int, user_id: int):
    """
    Deletes an item and logs the activity.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return

        with conn.cursor() as cursor:
            # Log first, then delete
            _log_activity(cursor, user_id, 'DELETE_ITEM', item_record_id, 'item')
            cursor.execute("DELETE FROM items WHERE item_record_id = %s", (item_record_id,))
            conn.commit()
    except psycopg2.Error as e:
        print(f"DB Error in delete_item: {e}")
    finally:
        if conn:
            conn.close()

def delete_all_items_in_container(container_id: int, user_id: int):
    """
    Deletes all items in a container and logs the activity.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return 0

        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM items WHERE container_id = %s", (container_id,))
            count = cursor.rowcount
            if count > 0:
                _log_activity(cursor, user_id, 'DELETE_ALL_ITEMS', container_id, 'container', f"Deleted {count} items.")
            conn.commit()
            return count
    except psycopg2.Error as e:
        print(f"DB Error in delete_all_items_in_container: {e}")
        return 0
    finally:
        if conn:
            conn.close()

# --- Share and Permission Functions ---
def can_user_add_admins(user_id: int, content_id: int) -> bool:
    """
    Checks if a user is an owner or an admin with rights to add other admins.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return False
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # أولاً، تحقق مما إذا كان المستخدم هو المالك
            cursor.execute("SELECT owner_user_id FROM containers WHERE id = %s", (content_id,))
            owner_res = cursor.fetchone()
            if owner_res and owner_res['owner_user_id'] == user_id:
                return True

            # ثانيًا، تحقق من جدول الصلاحيات
            cursor.execute(
                "SELECT can_add_admins FROM permissions WHERE user_id = %s AND content_id = %s AND permission_level = 'admin'",
                (user_id, content_id)
            )
            perm_res = cursor.fetchone()
            return perm_res and perm_res['can_add_admins'] == 1
    except psycopg2.Error as e:
        print(f"DB Error in can_user_add_admins: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_or_create_viewer_share_link(owner_user_id: int, content_type: str, content_id: int) -> str:
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return None

        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT share_token FROM shares WHERE content_type = %s AND content_id = %s AND link_type = 'viewer'",
                (content_type, content_id)
            )
            existing_link = cursor.fetchone()
            if existing_link:
                return existing_link[0]
            else:
                token = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO shares (share_token, content_type, content_id, owner_user_id, link_type) VALUES (%s, %s, %s, %s, %s)",
                    (token, content_type, content_id, owner_user_id, 'viewer')
                )
                _log_activity(cursor, owner_user_id, 'CREATE_SHARE_LINK', content_id, content_type, "Type: viewer")
                conn.commit()
                return token
    except psycopg2.Error as e:
        print(f"DB Error in get_or_create_viewer_share_link: {e}")
        return None
    finally:
        if conn:
            conn.close()

def create_share_link(owner_user_id: int, content_type: str, content_id: int, link_type: str, grants_can_add_admins: int = 0) -> str: # تعديل هنا
    token = str(uuid.uuid4())
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return None

        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO shares (share_token, content_type, content_id, owner_user_id, link_type, grants_can_add_admins) VALUES (%s, %s, %s, %s, %s, %s)", # تعديل هنا
                (token, content_type, content_id, owner_user_id, link_type, grants_can_add_admins) # تعديل هنا
            )
            _log_activity(cursor, owner_user_id, 'CREATE_SHARE_LINK', content_id, content_type, f"Type: {link_type}, Can Add Admins: {grants_can_add_admins}")
            conn.commit()
            return token
    except psycopg2.Error as e:
        print(f"DB Error in create_share_link: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_share_by_token(token: str):
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return None

        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT * FROM shares WHERE share_token = %s", (token,))
            return cursor.fetchone()
    except psycopg2.Error as e:
        print(f"DB Error in get_share_by_token: {e}")
        return None
    finally:
        if conn:
            conn.close()

def deactivate_share_link(token: str, user_id: int):
    """ Logs who used the link """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return

        with conn.cursor() as cursor:
            cursor.execute("UPDATE shares SET is_used = TRUE WHERE share_token = %s", (token,))
            _log_activity(cursor, user_id, 'USE_SHARE_LINK', details=f"Token: {token}")
            conn.commit()
    except psycopg2.Error as e:
        print(f"DB Error in deactivate_share_link: {e}")
    finally:
        if conn:
            conn.close()

def grant_permission(user_id: int, content_type: str, content_id: int, new_permission_level: str, can_add_admins: int = 0): # تعديل هنا
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return

        with conn.cursor() as cursor:
            # إذا كان المستخدم هو المالك، يجب أن يحصل على صلاحية إضافة المشرفين دائمًا
            details = get_container_details(content_id)
            if details and details['owner_user_id'] == user_id:
                new_permission_level = 'owner'
                can_add_admins = 1

            query = """
                INSERT INTO permissions (user_id, content_type, content_id, permission_level, can_add_admins)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id, content_id, content_type) DO UPDATE SET
                    permission_level = EXCLUDED.permission_level,
                    can_add_admins = EXCLUDED.can_add_admins
                WHERE
                    (permissions.permission_level = 'viewer' AND EXCLUDED.permission_level = 'admin') OR
                    (permissions.permission_level = 'admin' AND EXCLUDED.permission_level = 'admin');
            """
            cursor.execute(query, (user_id, content_type, content_id, new_permission_level, can_add_admins)) # تعديل هنا

            if cursor.rowcount > 0:
                _log_activity(cursor, user_id, 'GRANT_PERMISSION', content_id, content_type, f"Level: {new_permission_level}, Can Add Admins: {can_add_admins}")
            conn.commit()
    except psycopg2.Error as e:
        print(f"DB Error in grant_permission: {e}")
    finally:
        if conn:
            conn.close()


def grant_viewer_permission_for_section(user_id: int, section_id: int):
    """
    [جديد] يمنح صلاحية مشاهدة لقسم معين بشكل آمن.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return

        with conn.cursor() as cursor:
            # يضيف الصلاحية فقط إذا لم تكن موجودة، أو يتجاهل الأمر إذا كانت موجودة
            # هذا يمنع تخفيض صلاحية المشرف إلى مشاهد
            query = """
                INSERT INTO permissions (user_id, content_type, content_id, permission_level)
                VALUES (%s, 'section', %s, 'viewer')
                ON CONFLICT (user_id, content_id, content_type) DO NOTHING;
            """
            cursor.execute(query, (user_id, section_id))
            if cursor.rowcount > 0:
                _log_activity(cursor, user_id, 'GRANT_PERMISSION', section_id, 'section', "Level: viewer (via channel button)")
            conn.commit()
    except psycopg2.Error as e:
        print(f"DB Error in grant_viewer_permission_for_section: {e}")
    finally:
        if conn:
            conn.close()

def revoke_permission(user_id: int, content_type: str, content_id: int):
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return

        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM permissions WHERE user_id = %s AND content_type = %s AND content_id = %s",
                (user_id, content_type, content_id)
            )
            if cursor.rowcount > 0:
                 _log_activity(cursor, user_id, 'REVOKE_PERMISSION', content_id, content_type)
            conn.commit()
    except psycopg2.Error as e:
        print(f"DB Error in revoke_permission: {e}")
    finally:
        if conn:
            conn.close()

def has_direct_permission(user_id: int, content_type: str, content_id: int) -> bool:
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return False

        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM permissions WHERE user_id = %s AND content_type = %s AND content_id = %s",
                (user_id, content_type, content_id)
            )
            return cursor.fetchone() is not None
    except psycopg2.Error as e:
        print(f"DB Error in has_direct_permission: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_permission_level(user_id: int, content_type: str, content_id: int) -> str | None:
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return None

        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # 1. Check for ownership
            cursor.execute("SELECT owner_user_id FROM containers WHERE id = %s", (content_id,))
            owner_result = cursor.fetchone()
            if owner_result and owner_result['owner_user_id'] == user_id:
                return 'owner'

            # 2. Hierarchically search for permissions
            current_id = content_id
            while current_id is not None:
                cursor.execute(
                    "SELECT permission_level FROM permissions WHERE user_id = %s AND content_id = %s",
                    (user_id, current_id)
                )
                permission_result = cursor.fetchone()
                if permission_result:
                    return permission_result['permission_level']

                # Move to the parent container
                cursor.execute("SELECT parent_id FROM containers WHERE id = %s", (current_id,))
                parent_result = cursor.fetchone()
                current_id = parent_result['parent_id'] if parent_result else None
            
            return None
    except psycopg2.Error as e:
        print(f"DB Error in get_permission_level: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_back_navigation(user_id: int, container_id: int) -> str:
    details = get_container_details(container_id)
    if not details: return "my_space"

    is_owner = details['owner_user_id'] == user_id
    parent_id = details['parent_id']

    if parent_id:
        parent_permission = get_permission_level(user_id, 'section', parent_id)
        if parent_permission:
            return f"container:{parent_id}"
        else:
            return "shared_spaces"
    else:
        return "my_space" if is_owner else "shared_spaces"

def get_shared_containers_for_user(user_id: int):
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return []

        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            query = """
                SELECT c.id, c.name, c.type, c.owner_user_id, p.permission_level
                FROM containers c
                JOIN permissions p ON c.id = p.content_id
                WHERE p.user_id = %(user_id)s
            """
            cursor.execute(query, {'user_id': user_id})
            return cursor.fetchall()
    except psycopg2.Error as e:
        print(f"DB Error in get_shared_containers_for_user: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_container_statistics(container_id: int) -> dict:
    """
    [جديد] يحسب إحصائيات الحاوية: عدد المشتركين وعدد المشرفين.
    """
    stats = {'admin_count': 0, 'subscriber_count': 0}
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return stats

        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # First, get the owner's ID
            cursor.execute("SELECT owner_user_id FROM containers WHERE id = %s", (container_id,))
            owner_result = cursor.fetchone()
            if not owner_result:
                return stats # Container not found
            owner_id = owner_result['owner_user_id']

            # Count admins (excluding the owner)
            cursor.execute(
                "SELECT COUNT(*) FROM permissions WHERE content_id = %s AND permission_level = 'admin' AND user_id != %s",
                (container_id, owner_id)
            )
            stats['admin_count'] = cursor.fetchone()[0]

            # Count all subscribers (admins + viewers, excluding the owner)
            # This counts distinct users to avoid double counting if a user has multiple entries for some reason
            cursor.execute(
                "SELECT COUNT(DISTINCT user_id) FROM permissions WHERE content_id = %s AND user_id != %s",
                (container_id, owner_id)
            )
            stats['subscriber_count'] = cursor.fetchone()[0]
            
            return stats
            
    except psycopg2.Error as e:
        print(f"DB Error in get_container_statistics: {e}")
        return stats # Return default stats on error
    finally:
        if conn:
            conn.close()

# --- Linking Token Functions ---

def create_linking_token(user_id: int, container_id: int) -> str | None:
    """
    [جديد] ينشئ رمزًا فريدًا لربط المجموعة ويحفظه في قاعدة البيانات.
    """
    token = str(uuid.uuid4())
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return None
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO linking_tokens (token, user_id, container_id, created_at) VALUES (%s, %s, %s, NOW())",
                (token, user_id, container_id)
            )
            conn.commit()
            return token
    except psycopg2.Error as e:
        print(f"DB Error in create_linking_token: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_linking_token_data(token: str):
    """
    [جديد] يجلب بيانات الرمز المؤقت للربط.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return None
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # Tokens are valid for a short period, e.g., 10 minutes.
            cursor.execute("SELECT * FROM linking_tokens WHERE token = %s AND created_at > NOW() - INTERVAL '10 minutes'", (token,))
            return cursor.fetchone()
    except psycopg2.Error as e:
        print(f"DB Error in get_linking_token_data: {e}")
        return None
    finally:
        if conn:
            conn.close()

def delete_linking_token(token: str):
    """
    [جديد] يحذف الرمز المؤقت بعد استخدامه.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM linking_tokens WHERE token = %s", (token,))
            conn.commit()
    except psycopg2.Error as e:
        print(f"DB Error in delete_linking_token: {e}")
    finally:
        if conn:
            conn.close()


# --- Entity Linking Functions ---

def link_entity(container_id: int, user_id: int, entity_id: int, entity_name: str, entity_type: str, is_group_with_topics: bool = False) -> bool:
    """
    [معدل] يضيف أو يحدث ربط كيان (قناة أو مجموعة) بحاوية.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return False
        with conn.cursor() as cursor:
            # This logic first deletes any existing link for the container, then adds the new one.
            # This avoids unique constraint violations on entity_id if the user is re-linking the same channel
            # to a different container, and correctly handles re-linking to the same container.
            
            # First, remove any old link associated with this container_id to free it up.
            cursor.execute("DELETE FROM linked_entities WHERE container_id = %s", (container_id,))

            # Now, insert the new link.
            query = """
                INSERT INTO linked_entities (container_id, user_id, entity_id, entity_name, entity_type, is_group_with_topics, is_watching, link_date)
                VALUES (%s, %s, %s, %s, %s, %s, FALSE, NOW())
            """
            cursor.execute(query, (container_id, user_id, entity_id, entity_name, entity_type, is_group_with_topics))
            
            _log_activity(cursor, user_id, f'LINK_{entity_type.upper()}', container_id, 'container', f"Entity ID: {entity_id}")
            conn.commit()
            return True
    except psycopg2.Error as e:
        # This can still fail if the entity_id is already linked to a *different* container
        # due to the UNIQUE constraint on entity_id. This case is handled in the application logic.
        if e.pgcode == '23505': # unique_violation
            print(f"DB Warning in link_entity: Unique constraint violation on entity_id. This is expected if the entity is already linked elsewhere. {e}")
        else:
            print(f"DB Error in link_entity: {e}")
        if conn: conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def get_linked_entity_by_container(container_id: int):
    """[معدل] يجلب تفاصيل الكيان المرتبط عبر معرّف الحاوية."""
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return None
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT * FROM linked_entities WHERE container_id = %s", (container_id,))
            return cursor.fetchone()
    except psycopg2.Error as e:
        print(f"DB Error in get_linked_entity_by_container: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_linked_entity_by_entity_id(entity_id: int):
    """[معدل] يجلب تفاصيل الكيان المرتبط عبر معرّف الكيان (قناة/مجموعة)."""
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return None
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT * FROM linked_entities WHERE entity_id = %s", (entity_id,))
            return cursor.fetchone()
    except psycopg2.Error as e:
        print(f"DB Error in get_linked_entity_by_entity_id: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_all_watching_entities() -> list:
    """[معدل] يجلب كل الكيانات المرتبطة التي هي في وضع المراقبة."""
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return []
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT * FROM linked_entities WHERE is_watching = TRUE")
            return cursor.fetchall()
    except psycopg2.Error as e:
        print(f"DB Error in get_all_watching_entities: {e}")
        return []
    finally:
        if conn:
            conn.close()

def update_watching_status(container_id: int, is_watching: bool, user_id: int) -> bool:
    """[معدل] يحدث حالة المراقبة لكيان مرتبط."""
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return False
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE linked_entities SET is_watching = %s WHERE container_id = %s",
                (is_watching, container_id)
            )
            activity = 'START_ENTITY_WATCH' if is_watching else 'STOP_ENTITY_WATCH'
            _log_activity(cursor, user_id, activity, container_id, 'container')
            conn.commit()
            return True
    except psycopg2.Error as e:
        print(f"DB Error in update_watching_status: {e}")
        return False
    finally:
        if conn:
            conn.close()

def delete_linked_entity(container_id: int, user_id: int) -> bool:
    """[معدل] يحذف ربط كيان."""
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return False
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM linked_entities WHERE container_id = %s", (container_id,))
            _log_activity(cursor, user_id, 'UNLINK_ENTITY', container_id, 'container')
            conn.commit()
            return True
    except psycopg2.Error as e:
        print(f"DB Error in delete_linked_entity: {e}")
        return False
    finally:
        if conn:
            conn.close()


# --- Topic Functions ---

def add_or_update_topic(chat_id: int, thread_id: int, topic_name: str):
    """
    [جديد] يضيف موضوعًا جديدًا للمجموعة أو يحدث اسمه إذا كان موجودًا بالفعل.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return

        with conn.cursor() as cursor:
            query = """
                INSERT INTO forum_topics (chat_id, thread_id, topic_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (chat_id, thread_id) DO UPDATE SET
                    topic_name = EXCLUDED.topic_name;
            """
            cursor.execute(query, (chat_id, thread_id, topic_name))
            conn.commit()
    except psycopg2.Error as e:
        print(f"DB Error in add_or_update_topic: {e}")
    finally:
        if conn:
            conn.close()

def get_topic_name_by_thread_id(chat_id: int, thread_id: int) -> str | None:
    """
    [جديد] يجلب اسم الموضوع باستخدام معرّف المجموعة ومعرّف الموضوع (thread).
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return None

        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT topic_name FROM forum_topics WHERE chat_id = %s AND thread_id = %s",
                (chat_id, thread_id)
            )
            result = cursor.fetchone()
            return result[0] if result else None
    except psycopg2.Error as e:
        print(f"DB Error in get_topic_name_by_thread_id: {e}")
        return None
    finally:
        if conn:
            conn.close()


# --- Archived Content Functions ---

def add_archived_content(entity_id: int, message_id: int, container_id: int, item_id: int) -> bool:
    """[معدل] يضيف سجلاً لمحتوى مؤرشف لمنع التكرار."""
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return False
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO archived_content (entity_id, message_id, container_id, item_id) VALUES (%s, %s, %s, %s)",
                (entity_id, message_id, container_id, item_id)
            )
            conn.commit()
            return True
    except psycopg2.Error as e:
        if e.pgcode != '23505': # unique_violation
             print(f"DB Error in add_archived_content: {e}")
        if conn: conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def is_content_archived(entity_id: int, message_id: int, container_id: int) -> bool:
    """[معدل] يتحقق مما إذا كان محتوى معين قد تم أرشفته بالفعل في حاوية معينة."""
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return True # Fail safe
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM archived_content WHERE entity_id = %s AND message_id = %s AND container_id = %s",
                (entity_id, message_id, container_id)
            )
            return cursor.fetchone() is not None
    except psycopg2.Error as e:
        print(f"DB Error in is_content_archived: {e}")
        return True # Fail safe
    finally:
        if conn:
            conn.close()


def get_archived_folders_for_content(entity_id: int, message_id: int) -> dict:
    """
    [معدل] يجلب كل المجلدات التي تم أرشفة رسالة معينة فيها مع معرّف العنصر.
    Returns a dictionary of {folder_id: item_id}.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return {}
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT container_id, item_id FROM archived_content WHERE entity_id = %s AND message_id = %s",
                (entity_id, message_id)
            )
            return {row[0]: row[1] for row in cursor.fetchall()}
    except psycopg2.Error as e:
        print(f"DB Error in get_archived_folders_for_content: {e}")
        return {}
    finally:
        if conn:
            conn.close()


def remove_archived_content(entity_id: int, message_id: int, container_id: int):
    """
    [معدل] يزيل سجل محتوى مؤرشف من مجلد معين.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM archived_content WHERE entity_id = %s AND message_id = %s AND container_id = %s",
                (entity_id, message_id, container_id)
            )
            conn.commit()
    except psycopg2.Error as e:
        print(f"DB Error in remove_archived_content: {e}")
    finally:
        if conn:
            conn.close()
