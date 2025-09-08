# database_setup.py

import psycopg2
import config

def setup_database():
    """
    Connects to the PostgreSQL database and creates the tables if they don't exist.
    """
    conn = None
    try:
        # 1. Connect to the PostgreSQL database
        conn = psycopg2.connect(
            dbname=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASS,
            host=config.DB_HOST
        )
        print("Successfully connected to the database.")

        # 2. Create a cursor
        cursor = conn.cursor()

        # --- Users Table ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            first_name TEXT NOT NULL
        )
        """)

        # --- Containers Table (for sections and folders) ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS containers (
            id SERIAL PRIMARY KEY,
            owner_user_id BIGINT NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL, -- 'section' or 'folder'
            parent_id INTEGER,
            FOREIGN KEY (owner_user_id) REFERENCES users (user_id) ON DELETE CASCADE,
            FOREIGN KEY (parent_id) REFERENCES containers (id) ON DELETE CASCADE
        )
        """)
        
        # --- Items Table (files and messages) ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            item_record_id SERIAL PRIMARY KEY,
            container_id INTEGER NOT NULL,
            file_unique_id TEXT,
            file_id TEXT,
            item_name TEXT,
            item_type TEXT NOT NULL,
            content TEXT,
            FOREIGN KEY (container_id) REFERENCES containers (id) ON DELETE CASCADE
        )
        """)

        # --- Share Tokens Table ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS shares (
            share_id SERIAL PRIMARY KEY,
            share_token TEXT NOT NULL UNIQUE,
            content_type TEXT NOT NULL, -- 'section' or 'folder'
            content_id INTEGER NOT NULL,
            owner_user_id BIGINT NOT NULL,
            link_type TEXT NOT NULL, -- 'viewer' or 'admin'
            is_used BOOLEAN NOT NULL DEFAULT FALSE,
            FOREIGN KEY (owner_user_id) REFERENCES users (user_id) ON DELETE CASCADE
        )
        """)

        # --- Permissions Table ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS permissions (
            permission_id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            content_type TEXT NOT NULL, -- 'section' or 'folder'
            content_id INTEGER NOT NULL,
            permission_level TEXT NOT NULL, -- 'viewer' or 'admin'
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
            UNIQUE (user_id, content_id, content_type)
        )
        """)

        # --- Add Indexes for performance ---
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_container_id ON items (container_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_containers_parent_id ON containers (parent_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_containers_owner_id ON containers (owner_user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_permissions_user_id ON permissions (user_id);")


        # 4. Commit changes
        conn.commit()
        print("Database and tables have been successfully set up/updated!")

    except psycopg2.Error as e:
        print(f"Database error: {e}")
    finally:
        # 5. Close the connection
        if conn:
            cursor.close()
            conn.close()
            print("Database connection closed.")

# Script entry point
if __name__ == "__main__":
    setup_database()