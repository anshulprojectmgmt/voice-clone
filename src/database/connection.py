"""
Database Connection and Initialization
Supports both SQLite (local) and PostgreSQL (production)
"""
import os
import logging
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Detect database type from environment
DATABASE_URL = os.getenv("DATABASE_URL")
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    logger.info("Using PostgreSQL database")
else:
    import sqlite3
    DB_PATH = Path(__file__).parents[2] / "data" / "stories.db"
    logger.info(f"Using SQLite database at: {DB_PATH}")


@contextmanager
def get_db():
    """Get database connection (context manager)"""
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            yield conn
        finally:
            conn.close()
    else:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


def get_cursor(conn):
    """Get cursor with appropriate row factory"""
    if USE_POSTGRES:
        return conn.cursor(cursor_factory=RealDictCursor)
    else:
        return conn.cursor()


def init_db():
    """Initialize database schema"""
    with get_db() as conn:
        cursor = get_cursor(conn)

        if USE_POSTGRES:
            # PostgreSQL schema
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

            # Create index for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at
                ON stories(created_at DESC)
            """)
        else:
            # SQLite schema
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

            # Create index for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at
                ON stories(created_at DESC)
            """)

        conn.commit()

        if USE_POSTGRES:
            logger.info("PostgreSQL database initialized")
        else:
            logger.info(f"SQLite database initialized at: {DB_PATH}")


if __name__ == "__main__":
    init_db()
    if USE_POSTGRES:
        print("✅ PostgreSQL database initialized successfully")
    else:
        print(f"✅ SQLite database initialized successfully at: {DB_PATH}")
