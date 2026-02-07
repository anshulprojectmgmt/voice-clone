"""
Database Connection and Initialization
Supports both SQLite (local) and PostgreSQL (production)
Render / RunPod SAFE with SSL, Retry, and Keepalives
"""

import os
import time
import logging
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# --------------------------------------------------
# Detect database type
# --------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USE_POSTGRES = bool(DATABASE_URL)

# Ensure SSL is always required (Render requirement)
if USE_POSTGRES and "sslmode" not in DATABASE_URL:
    DATABASE_URL += "?sslmode=require"

if USE_POSTGRES:
    import psycopg2
    from psycopg2 import OperationalError
    from psycopg2.extras import RealDictCursor

    logger.info("Using PostgreSQL database")
else:
    import sqlite3

    DB_PATH = Path(__file__).parents[2] / "data" / "stories.db"
    logger.info(f"Using SQLite database at: {DB_PATH}")


# --------------------------------------------------
# Database Connection (with retry + keepalive)
# --------------------------------------------------
@contextmanager
def get_db():
    conn = None

    if USE_POSTGRES:
        max_retries = 3

        for attempt in range(max_retries):
            try:
                conn = psycopg2.connect(
                    DATABASE_URL,
                    sslmode="require",
                    connect_timeout=10,
                    keepalives=1,
                    keepalives_idle=30,
                    keepalives_interval=10,
                    keepalives_count=5,
                    gssencmode='disable'
                )
                conn.autocommit = True
                break
            except OperationalError as e:
                # Retry ONLY on connection / SSL issues
                if "SSL" not in str(e) and "connection" not in str(e):
                    raise

                logger.warning(
                    f"Database connection failed "
                    f"(attempt {attempt + 1}/{max_retries}): {e}"
                )

                if attempt == max_retries - 1:
                    raise

                time.sleep(1)

        try:
            yield conn
        finally:
            if conn:
                conn.close()

    else:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


# --------------------------------------------------
# Cursor helper
# --------------------------------------------------
def get_cursor(conn):
    if USE_POSTGRES:
        return conn.cursor(cursor_factory=RealDictCursor)
    return conn.cursor()


# --------------------------------------------------
# Database Initialization
# --------------------------------------------------
def init_db():
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
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS voice_profiles (
                    voice_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    name TEXT,
                    description TEXT,
                    file_path TEXT,
                    sample_rate INTEGER,
                    duration REAL,
                    is_default INTEGER DEFAULT 0,
                    usage_count INTEGER DEFAULT 0,
                    last_used TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    speaker_embedding TEXT
                )
            """)

        conn.commit()

        if USE_POSTGRES:
            logger.info("PostgreSQL database initialized")
        else:
            logger.info(f"SQLite database initialized at: {DB_PATH}")


# --------------------------------------------------
# Manual init support
# --------------------------------------------------
if __name__ == "__main__":
    init_db()
    print("✅ Database initialized successfully")
