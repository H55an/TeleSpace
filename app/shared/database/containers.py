import psycopg2
import psycopg2.extras
from .core import get_db_connection, _log_activity
# --- Container Functions (Unified) ---

# Note: Imported by auth.py, so try to avoid circular imports.
# This module depends on 'auth' ONLY for 'get_root_containers' query if we used python logic,
# but 'get_root_containers' uses RAW SQL JOIN on permissions table, so no direct python dependency on auth.py.
# However, 'get_permission_level' is in auth.py, used by get_back_navigation.
# Let's see if we need get_permission_level here.
# 'get_back_navigation' uses 'get_permission_level'.
# So we need to import access to permission level.
# To avoid circle: 'get_permission_level' is in auth.py.
# 'auth.py' needs 'get_container_details' from here.
# Solution: Import inside function to avoid top-level circle.

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

def get_back_navigation(user_id: int, container_id: int) -> str:
    # Avoid circular import by importing inside function
    from .auth import get_permission_level
    
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
