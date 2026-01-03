"""
Migration 001: Add Authentication and Voice Profiles

Creates tables for:
- users (JWT authentication)
- voice_profiles (voice embeddings caching)
- refresh_tokens (JWT refresh token rotation)
- Alters stories table to add user_id foreign key
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parents[2]))

from database.connection import get_db, get_cursor, USE_POSTGRES
import logging

logger = logging.getLogger(__name__)


def migrate_up():
    """Run migration - create new tables"""
    logger.info("Running migration 001: Add authentication and voice profiles")

    with get_db() as conn:
        cursor = get_cursor(conn)

        # First, ensure stories table exists (from init_db)
        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stories (
                    id VARCHAR(255) PRIMARY KEY,
                    title TEXT,
                    text TEXT NOT NULL,
                    theme VARCHAR(50) NOT NULL,
                    style VARCHAR(50) NOT NULL,
                    tone VARCHAR(50) NOT NULL,
                    length VARCHAR(20) NOT NULL,
                    word_count INTEGER NOT NULL,
                    thumbnail_color VARCHAR(20),
                    preview_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    audio_url TEXT,
                    metadata TEXT
                )
            """)
            logger.info("  ✓ Ensured stories table exists")
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stories (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    text TEXT NOT NULL,
                    theme TEXT NOT NULL,
                    style TEXT NOT NULL,
                    tone TEXT NOT NULL,
                    length TEXT NOT NULL,
                    word_count INTEGER NOT NULL,
                    thumbnail_color TEXT,
                    preview_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    audio_url TEXT,
                    metadata TEXT
                )
            """)
            logger.info("  ✓ Ensured stories table exists")

        if USE_POSTGRES:
            # PostgreSQL schema
            logger.info("Creating PostgreSQL tables...")

            # 1. Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    is_verified BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    metadata TEXT
                )
            """)
            logger.info("  ✓ Created users table")

            # Create indexes for users
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_username
                ON users(username)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_email
                ON users(email)
            """)

            # 2. Voice profiles table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS voice_profiles (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    voice_id VARCHAR(255) UNIQUE NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    file_path VARCHAR(500) NOT NULL,
                    embeddings_path VARCHAR(500),
                    sample_rate INTEGER DEFAULT 24000,
                    duration FLOAT,
                    is_default BOOLEAN DEFAULT FALSE,
                    exaggeration FLOAT DEFAULT 0.3,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP,
                    usage_count INTEGER DEFAULT 0
                )
            """)
            logger.info("  ✓ Created voice_profiles table")

            # Create indexes for voice_profiles
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_voice_user_id
                ON voice_profiles(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_voice_voice_id
                ON voice_profiles(voice_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_voice_default
                ON voice_profiles(user_id, is_default)
            """)

            # 3. Refresh tokens table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    token VARCHAR(500) UNIQUE NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    revoked_at TIMESTAMP,
                    is_revoked BOOLEAN DEFAULT FALSE
                )
            """)
            logger.info("  ✓ Created refresh_tokens table")

            # Create indexes for refresh_tokens
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_refresh_token
                ON refresh_tokens(token)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_refresh_user
                ON refresh_tokens(user_id)
            """)

            # 4. Alter stories table (add user_id)
            # Check if column exists first
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='stories' AND column_name='user_id'
            """)
            if not cursor.fetchone():
                cursor.execute("""
                    ALTER TABLE stories
                    ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_stories_user_id
                    ON stories(user_id)
                """)
                logger.info("  ✓ Added user_id to stories table")
            else:
                logger.info("  - stories.user_id already exists")

        else:
            # SQLite schema
            logger.info("Creating SQLite tables...")

            # 1. Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    is_verified INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    metadata TEXT
                )
            """)
            logger.info("  ✓ Created users table")

            # Create indexes for users
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_username
                ON users(username)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_email
                ON users(email)
            """)

            # 2. Voice profiles table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS voice_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    voice_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    file_path TEXT NOT NULL,
                    embeddings_path TEXT,
                    sample_rate INTEGER DEFAULT 24000,
                    duration REAL,
                    is_default INTEGER DEFAULT 0,
                    exaggeration REAL DEFAULT 0.3,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP,
                    usage_count INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            logger.info("  ✓ Created voice_profiles table")

            # Create indexes for voice_profiles
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_voice_user_id
                ON voice_profiles(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_voice_voice_id
                ON voice_profiles(voice_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_voice_default
                ON voice_profiles(user_id, is_default)
            """)

            # 3. Refresh tokens table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    revoked_at TIMESTAMP,
                    is_revoked INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            logger.info("  ✓ Created refresh_tokens table")

            # Create indexes for refresh_tokens
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_refresh_token
                ON refresh_tokens(token)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_refresh_user
                ON refresh_tokens(user_id)
            """)

            # 4. Alter stories table (add user_id)
            # SQLite doesn't support ALTER TABLE ADD COLUMN with FOREIGN KEY directly
            # Check if column exists
            cursor.execute("PRAGMA table_info(stories)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'user_id' not in columns:
                cursor.execute("""
                    ALTER TABLE stories
                    ADD COLUMN user_id INTEGER
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_stories_user_id
                    ON stories(user_id)
                """)
                logger.info("  ✓ Added user_id to stories table")
            else:
                logger.info("  - stories.user_id already exists")

        # 5. Create system user for default voices
        cursor.execute("""
            INSERT OR IGNORE INTO users (id, username, email, password_hash, is_active)
            VALUES (1, 'system', 'system@voiceclone.local', 'none', TRUE)
        """ if not USE_POSTGRES else """
            INSERT INTO users (id, username, email, password_hash, is_active)
            VALUES (1, 'system', 'system@voiceclone.local', 'none', TRUE)
            ON CONFLICT (username) DO NOTHING
        """)
        logger.info("  ✓ Created system user (id=1)")

        conn.commit()
        logger.info("Migration 001 completed successfully")


def migrate_down():
    """Rollback migration - drop tables in reverse order"""
    logger.info("Rolling back migration 001")

    with get_db() as conn:
        cursor = get_cursor(conn)

        # Remove user_id from stories
        if USE_POSTGRES:
            cursor.execute("ALTER TABLE stories DROP COLUMN IF EXISTS user_id")
        else:
            # SQLite doesn't support DROP COLUMN easily, skip for now
            logger.warning("  - Cannot drop user_id from stories in SQLite")

        # Drop tables
        cursor.execute("DROP TABLE IF EXISTS refresh_tokens")
        cursor.execute("DROP TABLE IF EXISTS voice_profiles")
        cursor.execute("DROP TABLE IF EXISTS users")

        conn.commit()
        logger.info("Migration 001 rolled back successfully")


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Database migration 001")
    parser.add_argument("--rollback", action="store_true", help="Rollback migration")
    args = parser.parse_args()

    if args.rollback:
        migrate_down()
    else:
        migrate_up()
