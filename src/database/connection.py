"""
Database Connection and Initialization
Supports both SQLite (local) and PostgreSQL (production) with Auto-Retry and Keepalives
"""
import os
import time
import logging
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Detect database type from environment
DATABASE_URL = os.getenv("DATABASE_URL")
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    import psycopg2
    from psycopg2 import OperationalError
    from psycopg2.extras import RealDictCursor
    logger.info("Using PostgreSQL database")
else:
    import sqlite3
    DB_PATH = Path(__file__).parents[2] / "data" / "stories.db"
    logger.info(f"Using SQLite database at: {DB_PATH}")


@contextmanager
def get_db():
    """Get database connection (context manager) with Retry Logic"""
    conn = None
    if USE_POSTGRES:
        # ---------------------------------------------------------
        # ROBUST CONNECTION STRATEGY: Retry up to 3 times
        # ---------------------------------------------------------
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Add TCP Keepalives to prevent "SSL Closed Unexpectedly"
                conn = psycopg2.connect(
                    DATABASE_URL,
                    sslmode='require',        # Force SSL
                    connect_timeout=10,       # Fail fast if hanging
                    keepalives=1,             # Enable TCP keepalives
                    keepalives_idle=30,       # Send ping after 30s idle
                    keepalives_interval=10,   # Ping every 10s
                    keepalives_count=5        # Drop after 5 failed pings
                )
                break  # If successful, exit the loop
            except OperationalError as e:
                logger.warning(f"Database connection failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    # If this was the last attempt, crash loudly
                    raise e
                time.sleep(1)  # Wait 1 second before retrying

        try:
            yield conn
        finally:
            if conn:
                conn.close()

    else:
        # SQLite Logic (unchanged)
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
    # (Your existing init_db code remains exactly the same)
    with get_db() as conn:
        cursor = get_cursor(conn)

        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS voice_profiles (
                    voice_id VARCHAR(255) PRIMARY KEY,
                    user_id INTEGER,
                    name VARCHAR(255),
                    description TEXT,
                    file_path TEXT,
                    sample_rate INTEGER,
                    duration FLOAT,
                    is_default BOOLEAN DEFAULT FALSE,
                    usage_count INTEGER DEFAULT 0,
                    last_used TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    speaker_embedding TEXT
                )
            """)
             # Add other tables if needed...
        
        conn.commit()

        if USE_POSTGRES:
            logger.info("PostgreSQL database initialized")
        else:
            logger.info(f"SQLite database initialized at: {DB_PATH}")

if __name__ == "__main__":
    init_db()