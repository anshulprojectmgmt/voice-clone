"""
DB Migration: Add speaker_embedding column to voice_profiles
Run this ONCE.
"""

from src.database.connection import get_db, get_cursor, USE_POSTGRES
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    with get_db() as conn:
        cursor = get_cursor(conn)

        try:
            if USE_POSTGRES:
                logger.info("Running PostgreSQL migration...")
                cursor.execute("""
                    ALTER TABLE voice_profiles
                    ADD COLUMN IF NOT EXISTS speaker_embedding JSONB
                """)
            else:
                logger.info("Running SQLite migration...")
                cursor.execute("""
                    ALTER TABLE voice_profiles
                    ADD COLUMN speaker_embedding TEXT
                """)

            conn.commit()
            logger.info("✅ Migration successful")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            conn.rollback()


if __name__ == "__main__":
    migrate()
