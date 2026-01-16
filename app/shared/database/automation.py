import psycopg2
import psycopg2.extras
import uuid
from .core import get_db_connection, _log_activity

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
