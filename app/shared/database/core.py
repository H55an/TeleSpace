import psycopg2
import psycopg2.extras
from app.shared import config

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
