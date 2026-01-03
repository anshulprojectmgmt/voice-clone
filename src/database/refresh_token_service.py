"""
Refresh Token Service - Database operations for JWT refresh token rotation
"""
import logging
from typing import Optional
from datetime import datetime, timedelta

from .connection import get_db, get_cursor
from .models import RefreshToken

logger = logging.getLogger(__name__)


def create_refresh_token(user_id: int, token: str, expires_days: int = 7) -> Optional[RefreshToken]:
    """
    Create a new refresh token

    Args:
        user_id: User ID
        token: Refresh token string
        expires_days: Days until expiration (default 7)

    Returns:
        RefreshToken object if successful, None otherwise
    """
    try:
        expires_at = datetime.now() + timedelta(days=expires_days)

        with get_db() as conn:
            cursor = get_cursor(conn)

            cursor.execute("""
                INSERT INTO refresh_tokens (user_id, token, expires_at)
                VALUES (?, ?, ?)
            """, (user_id, token, expires_at.isoformat()))

            token_id = cursor.lastrowid
            cursor.execute("SELECT * FROM refresh_tokens WHERE id = ?", (token_id,))
            row = cursor.fetchone()

            conn.commit()

            if row:
                refresh_token = RefreshToken.from_db_row(row)
                logger.info(f"Created refresh token for user {user_id}")
                return refresh_token

            return None
    except Exception as e:
        logger.error(f"Failed to create refresh token for user {user_id}: {e}")
        return None


def get_refresh_token(token: str) -> Optional[RefreshToken]:
    """Get refresh token by token string"""
    try:
        with get_db() as conn:
            cursor = get_cursor(conn)
            cursor.execute("SELECT * FROM refresh_tokens WHERE token = ?", (token,))
            row = cursor.fetchone()

            if row:
                return RefreshToken.from_db_row(row)
            return None
    except Exception as e:
        logger.error(f"Failed to get refresh token: {e}")
        return None


def is_token_valid(token: str) -> bool:
    """
    Check if refresh token is valid (exists, not revoked, not expired)

    Args:
        token: Refresh token string

    Returns:
        True if valid, False otherwise
    """
    try:
        refresh_token = get_refresh_token(token)
        if not refresh_token:
            return False

        # Check if revoked
        if refresh_token.is_revoked:
            logger.warning("Token is revoked")
            return False

        # Check if expired
        expires_at = datetime.fromisoformat(refresh_token.expires_at)
        if datetime.now() > expires_at:
            logger.warning("Token is expired")
            return False

        return True
    except Exception as e:
        logger.error(f"Failed to validate token: {e}")
        return False


def revoke_token(token: str) -> bool:
    """
    Revoke a refresh token

    Args:
        token: Token string to revoke

    Returns:
        True if revoked, False otherwise
    """
    try:
        with get_db() as conn:
            cursor = get_cursor(conn)

            cursor.execute("""
                UPDATE refresh_tokens
                SET is_revoked = 1, revoked_at = CURRENT_TIMESTAMP
                WHERE token = ?
            """, (token,))

            conn.commit()

            revoked = cursor.rowcount > 0
            if revoked:
                logger.info("Revoked refresh token")
            return revoked
    except Exception as e:
        logger.error(f"Failed to revoke token: {e}")
        return False


def revoke_user_tokens(user_id: int) -> int:
    """
    Revoke all refresh tokens for a user

    Args:
        user_id: User ID

    Returns:
        Number of tokens revoked
    """
    try:
        with get_db() as conn:
            cursor = get_cursor(conn)

            cursor.execute("""
                UPDATE refresh_tokens
                SET is_revoked = 1, revoked_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND is_revoked = 0
            """, (user_id,))

            conn.commit()

            count = cursor.rowcount
            logger.info(f"Revoked {count} tokens for user {user_id}")
            return count
    except Exception as e:
        logger.error(f"Failed to revoke tokens for user {user_id}: {e}")
        return 0


def cleanup_expired_tokens() -> int:
    """
    Delete expired refresh tokens (cleanup job)

    Returns:
        Number of tokens deleted
    """
    try:
        with get_db() as conn:
            cursor = get_cursor(conn)

            cursor.execute("""
                DELETE FROM refresh_tokens
                WHERE expires_at < CURRENT_TIMESTAMP
            """)

            conn.commit()

            count = cursor.rowcount
            if count > 0:
                logger.info(f"Deleted {count} expired tokens")
            return count
    except Exception as e:
        logger.error(f"Failed to cleanup expired tokens: {e}")
        return 0


def get_user_tokens_count(user_id: int) -> int:
    """Get count of active (non-revoked) tokens for a user"""
    try:
        with get_db() as conn:
            cursor = get_cursor(conn)

            cursor.execute("""
                SELECT COUNT(*) as count
                FROM refresh_tokens
                WHERE user_id = ? AND is_revoked = 0 AND expires_at > CURRENT_TIMESTAMP
            """, (user_id,))

            row = cursor.fetchone()
            return row['count'] if row else 0
    except Exception as e:
        logger.error(f"Failed to get token count for user {user_id}: {e}")
        return 0
