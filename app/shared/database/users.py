import psycopg2
from .core import get_db_connection, _log_activity

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

def get_user(user_id: int):
    """
    Retrieves user details.
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return None
        
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            return cursor.fetchone()
    except psycopg2.Error as e:
        print(f"DB Error in get_user: {e}")
        return None
    finally:
        if conn:
            conn.close()
