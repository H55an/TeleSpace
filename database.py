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
            dbname=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASS,
            host=config.DB_HOST
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
def add_item(container_id: int, user_id: int, item_name: str, item_type: str, content: str, file_unique_id: str = None, file_id: str = None):
    """
    Adds an item to a container and logs the activity.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return

        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO items (container_id, item_name, item_type, content, file_unique_id, file_id, upload_date) VALUES (%s, %s, %s, %s, %s, %s, NOW()) RETURNING item_record_id",
                (container_id, item_name, item_type, content, file_unique_id, file_id)
            )
            item_id = cursor.fetchone()[0]
            _log_activity(cursor, user_id, 'ADD_ITEM', item_id, 'item', f"Name: {item_name} in container {container_id}")
            conn.commit()
    except psycopg2.Error as e:
        print(f"DB Error in add_item: {e}")
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

def create_share_link(owner_user_id: int, content_type: str, content_id: int, link_type: str) -> str:
    token = str(uuid.uuid4())
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return None

        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO shares (share_token, content_type, content_id, owner_user_id, link_type) VALUES (%s, %s, %s, %s, %s)",
                (token, content_type, content_id, owner_user_id, link_type)
            )
            _log_activity(cursor, owner_user_id, 'CREATE_SHARE_LINK', content_id, content_type, f"Type: {link_type}")
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

def grant_permission(user_id: int, content_type: str, content_id: int, new_permission_level: str):
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return

        with conn.cursor() as cursor:
            query = """
                INSERT INTO permissions (user_id, content_type, content_id, permission_level)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, content_id, content_type) DO UPDATE SET
                    permission_level = EXCLUDED.permission_level
                WHERE
                    permissions.permission_level = 'viewer' AND EXCLUDED.permission_level = 'admin';
            """
            cursor.execute(query, (user_id, content_type, content_id, new_permission_level))
            # Log only if a row was actually affected
            if cursor.rowcount > 0:
                _log_activity(cursor, user_id, 'GRANT_PERMISSION', content_id, content_type, f"Level: {new_permission_level}")
            conn.commit()
    except psycopg2.Error as e:
        print(f"DB Error in grant_permission: {e}")
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
