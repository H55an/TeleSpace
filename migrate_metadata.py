import psycopg2
from app.shared import config

def run_migration():
    print("Starting migration...")
    conn = None
    try:
        conn = psycopg2.connect(config.DATABASE_URL)
        cursor = conn.cursor()

        # Users table updates
        print("Updating users table...")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name TEXT;")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT;")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS language_code TEXT;")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_premium BOOLEAN DEFAULT FALSE;")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_photo_path TEXT;")

        # Items table updates
        print("Updating items table...")
        cursor.execute("ALTER TABLE items ADD COLUMN IF NOT EXISTS file_name TEXT;")
        cursor.execute("ALTER TABLE items ADD COLUMN IF NOT EXISTS mime_type TEXT;")
        cursor.execute("ALTER TABLE items ADD COLUMN IF NOT EXISTS file_size BIGINT;")
        cursor.execute("ALTER TABLE items ADD COLUMN IF NOT EXISTS width INTEGER;")
        cursor.execute("ALTER TABLE items ADD COLUMN IF NOT EXISTS height INTEGER;")
        cursor.execute("ALTER TABLE items ADD COLUMN IF NOT EXISTS duration INTEGER;")
        cursor.execute("ALTER TABLE items ADD COLUMN IF NOT EXISTS thumbnail_path TEXT;")

        conn.commit()
        print("Migration completed successfully!")

    except Exception as e:
        print(f"Migration failed: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()

if __name__ == "__main__":
    run_migration()
