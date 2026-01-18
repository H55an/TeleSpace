# setup.py
import psycopg2
from app.shared import config

def setup_database():
    """
    Connects to the PostgreSQL database and creates/updates the tables to the latest schema.
    """
    conn = None
    try:
        conn = psycopg2.connect(config.DATABASE_URL)
        print("Successfully connected to the database.")
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

        # --- File Locations Table ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_locations (
            location_id SERIAL PRIMARY KEY,
            item_id INTEGER REFERENCES items(item_record_id) ON DELETE CASCADE,
            channel_id BIGINT NOT NULL,
            message_id INTEGER NOT NULL,
            UNIQUE(channel_id, message_id)
        );
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
            grants_can_add_admins INTEGER NOT NULL DEFAULT 0,
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
            can_add_admins INTEGER NOT NULL DEFAULT 0,
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

        # --- Linked Entities Table (for Channel/Group Watch feature) ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS linked_entities (
            id SERIAL PRIMARY KEY,
            container_id INTEGER NOT NULL UNIQUE,
            user_id BIGINT NOT NULL,
            entity_id BIGINT NOT NULL UNIQUE,
            entity_name TEXT,
            entity_type TEXT, -- 'channel', 'group', 'supergroup'
            is_group_with_topics BOOLEAN,
            is_watching BOOLEAN NOT NULL DEFAULT FALSE,
            link_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            FOREIGN KEY (container_id) REFERENCES containers (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        )
        """)

        # --- Archived Content Table (for preventing duplicates in Watch feature) ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS archived_content (
            id SERIAL PRIMARY KEY,
            entity_id BIGINT NOT NULL,
            message_id BIGINT NOT NULL,
            container_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            archive_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            FOREIGN KEY (container_id) REFERENCES containers (id) ON DELETE CASCADE,
            FOREIGN KEY (item_id) REFERENCES items (item_record_id) ON DELETE CASCADE,
            UNIQUE (entity_id, message_id, container_id)
        )
        """)

        # --- Linking Tokens Table (for Group Linking) ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS linking_tokens (
            token TEXT PRIMARY KEY,
            user_id BIGINT NOT NULL,
            container_id INTEGER NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
            FOREIGN KEY (container_id) REFERENCES containers (id) ON DELETE CASCADE
        )
        """)

        # --- Forum Topics Table (for Topic Name Memory) ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS forum_topics (
            chat_id BIGINT NOT NULL,
            thread_id BIGINT NOT NULL,
            topic_name TEXT NOT NULL,
            PRIMARY KEY (chat_id, thread_id)
        )
        """)

        # === PHASE 2 UPDATES: Mobile App & Auth Support ===

        # --- Auth Requests Table (Handshake) ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS auth_requests (
            request_id TEXT PRIMARY KEY,       -- The UUID generated by the mobile app
            user_id BIGINT,                    -- Filled by the bot when user clicks deep link
            access_token TEXT,                 -- The long-term token for the app API calls
            status TEXT DEFAULT 'pending',     -- 'pending', 'approved', 'expired'
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """)

        # --- App Sessions Table ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_sessions (
            session_id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            access_token TEXT NOT NULL UNIQUE,
            device_info TEXT,
            last_login TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            is_active BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        );
        """)

        # --- Add Indexes for performance ---
        print("Applying indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_container_id ON items (container_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_containers_parent_id ON containers (parent_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_containers_owner_id ON containers (owner_user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_permissions_user_id ON permissions (user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_log_user_id ON activity_log (user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_linked_entities_entity_id ON linked_entities (entity_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_archived_content_entity_id_message_id ON archived_content (entity_id, message_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_locations_item_id ON file_locations(item_id);")
        
        # New Index for Auth
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_requests_status ON auth_requests (status);")

        conn.commit()
        print("Database and tables have been successfully set up/updated!")

    except Exception as e:
        import traceback
        print(f"An error occurred in database_setup.py: {e}")
        traceback.print_exc()
    finally:
        if conn:
            cursor.close()
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    setup_database()
