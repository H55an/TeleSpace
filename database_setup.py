# database_setup.py

import psycopg2
import config

def setup_database():
    """
    Connects to the PostgreSQL database and creates/updates the tables.
    """
    conn = None
    try:
        # 1. Connect to the PostgreSQL database
        conn = psycopg2.connect(
            config.DATABASE_URL
        )
        print("Successfully connected to the database.")

        # 2. Create a cursor
        cursor = conn.cursor()

        # --- Users Table ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            first_name TEXT NOT NULL,
            join_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            last_active_date TIMESTAMP WITH TIME ZONE DEFAULT NOW()
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
            creation_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
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
            upload_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
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
            creation_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
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
            grant_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
            UNIQUE (user_id, content_id, content_type)
        )
        """)

        # --- Activity Log Table ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            log_id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            activity_type TEXT NOT NULL, -- e.g., 'CREATE_CONTAINER', 'DELETE_ITEM'
            target_id INTEGER,
            target_type TEXT, -- e.g., 'container', 'item'
            details TEXT, -- For extra info like new names, etc.
            activity_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        )
        """)

        # --- Channel Links Table (for Channel Watch feature) ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS channel_links (
            id SERIAL PRIMARY KEY,
            container_id INTEGER NOT NULL UNIQUE,
            user_id BIGINT NOT NULL,
            channel_id BIGINT NOT NULL UNIQUE,
            channel_name TEXT,
            is_watching BOOLEAN NOT NULL DEFAULT FALSE,
            link_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            FOREIGN KEY (container_id) REFERENCES containers (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        )
        """)

        # --- Archived Messages Table (for preventing duplicates in Channel Watch) ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS archived_messages (
            id SERIAL PRIMARY KEY,
            channel_id BIGINT NOT NULL,
            message_id BIGINT NOT NULL,
            container_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            archive_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            FOREIGN KEY (container_id) REFERENCES containers (id) ON DELETE CASCADE,
            FOREIGN KEY (item_id) REFERENCES items (item_record_id) ON DELETE CASCADE,
            UNIQUE (channel_id, message_id, container_id)
        )
        """)

        # --- Add/Update Columns (using a helper function to avoid errors on re-runs) ---
        def add_column_if_not_exists(table_name, column_name, column_definition):
            cursor.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='{table_name}' AND column_name='{column_name}'
            """)
            if not cursor.fetchone():
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")
                print(f"Added column '{column_name}' to table '{table_name}'.")

        # Add new columns to existing tables
        add_column_if_not_exists('users', 'join_date', 'TIMESTAMP WITH TIME ZONE DEFAULT NOW()')
        add_column_if_not_exists('users', 'last_active_date', 'TIMESTAMP WITH TIME ZONE DEFAULT NOW()')
        add_column_if_not_exists('containers', 'creation_date', 'TIMESTAMP WITH TIME ZONE DEFAULT NOW()')
        add_column_if_not_exists('items', 'upload_date', 'TIMESTAMP WITH TIME ZONE DEFAULT NOW()')
        add_column_if_not_exists('shares', 'creation_date', 'TIMESTAMP WITH TIME ZONE DEFAULT NOW()')
        add_column_if_not_exists('permissions', 'grant_date', 'TIMESTAMP WITH TIME ZONE DEFAULT NOW()')


        # --- Add Indexes for performance ---
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_container_id ON items (container_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_containers_parent_id ON containers (parent_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_containers_owner_id ON containers (owner_user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_permissions_user_id ON permissions (user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_log_user_id ON activity_log (user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_log_activity_type ON activity_log (activity_type);")

        # --- Indexes for Channel Watch ---
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_channel_links_channel_id ON channel_links (channel_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_archived_messages_channel_id_message_id ON archived_messages (channel_id, message_id);")


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
