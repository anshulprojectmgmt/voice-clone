"""
User Service - Database operations for user management
"""
import logging
from typing import Optional
from datetime import datetime

from .connection import get_db, get_cursor, USE_POSTGRES
from .models import User

logger = logging.getLogger(__name__)


def _format_query(query: str) -> str:
    """Convert SQL query placeholders for PostgreSQL compatibility"""
    if USE_POSTGRES:
        return query.replace('?', '%s')
    return query


def create_user(username: str, email: str, password_hash: str) -> Optional[User]:
    """
    Create a new user

    Args:
        username: Unique username
        email: Unique email address
        password_hash: Bcrypt hashed password

    Returns:
        User object if successful, None if username/email already exists
    """
    try:
        with get_db() as conn:
            cursor = get_cursor(conn)

            if USE_POSTGRES:
                cursor.execute("""
                    INSERT INTO users (username, email, password_hash)
                    VALUES (%s, %s, %s)
                    RETURNING id, username, email, password_hash, is_active, is_verified,
                              created_at, updated_at, last_login, metadata
                """, (username, email, password_hash))
                row = cursor.fetchone()
            else:
                cursor.execute("""
                    INSERT INTO users (username, email, password_hash)
                    VALUES (?, ?, ?)
                """, (username, email, password_hash))
                user_id = cursor.lastrowid
                cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
                row = cursor.fetchone()

            conn.commit()

            if row:
                user = User.from_db_row(row)
                logger.info(f"Created user: {username} (id={user.id})")
                return user

            return None
    except Exception as e:
        logger.error(f"Failed to create user {username}: {e}")
        return None


def get_user_by_id(user_id: int) -> Optional[User]:
    """Get user by ID"""
    try:
        with get_db() as conn:
            cursor = get_cursor(conn)
            cursor.execute(_format_query("SELECT * FROM users WHERE id = ?"), (user_id,))
            row = cursor.fetchone()

            if row:
                return User.from_db_row(row)
            return None
    except Exception as e:
        logger.error(f"Failed to get user by id {user_id}: {e}")
        return None


def get_user_by_username(username: str) -> Optional[User]:
    """Get user by username"""
    try:
        with get_db() as conn:
            cursor = get_cursor(conn)
            cursor.execute(_format_query("SELECT * FROM users WHERE username = ?"), (username,))
            row = cursor.fetchone()

            if row:
                return User.from_db_row(row)
            return None
    except Exception as e:
        logger.error(f"Failed to get user by username {username}: {e}")
        return None


def get_user_by_email(email: str) -> Optional[User]:
    """Get user by email"""
    try:
        with get_db() as conn:
            cursor = get_cursor(conn)
            cursor.execute(_format_query("SELECT * FROM users WHERE email = ?"), (email,))
            row = cursor.fetchone()

            if row:
                return User.from_db_row(row)
            return None
    except Exception as e:
        logger.error(f"Failed to get user by email {email}: {e}")
        return None


def authenticate_user(username: str, password_hash: str) -> Optional[User]:
    """
    Authenticate user by username and password hash

    Note: Password verification should be done with bcrypt in the auth layer.
    This method retrieves the user for password verification.

    Args:
        username: Username
        password_hash: Will be verified against stored hash

    Returns:
        User object if found, None otherwise
    """
    return get_user_by_username(username)


def update_last_login(user_id: int) -> bool:
    """Update user's last login timestamp"""
    try:
        with get_db() as conn:
            cursor = get_cursor(conn)

            cursor.execute(_format_query("""
                UPDATE users
                SET last_login = CURRENT_TIMESTAMP
                WHERE id = ?
            """), (user_id,))

            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update last login for user {user_id}: {e}")
        return False


def update_user(
    user_id: int,
    email: Optional[str] = None,
    password_hash: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_verified: Optional[bool] = None
) -> Optional[User]:
    """
    Update user fields

    Args:
        user_id: User ID to update
        email: New email (optional)
        password_hash: New password hash (optional)
        is_active: Active status (optional)
        is_verified: Verified status (optional)

    Returns:
        Updated User object or None if failed
    """
    try:
        updates = []
        params = []

        placeholder = "%s" if USE_POSTGRES else "?"

        if email is not None:
            updates.append(f"email = {placeholder}")
            params.append(email)
        if password_hash is not None:
            updates.append(f"password_hash = {placeholder}")
            params.append(password_hash)
        if is_active is not None:
            updates.append(f"is_active = {placeholder}")
            params.append(1 if is_active else 0)
        if is_verified is not None:
            updates.append(f"is_verified = {placeholder}")
            params.append(1 if is_verified else 0)

        if not updates:
            return get_user_by_id(user_id)

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(user_id)

        with get_db() as conn:
            cursor = get_cursor(conn)

            query = f"UPDATE users SET {', '.join(updates)} WHERE id = {placeholder}"
            cursor.execute(query, params)
            conn.commit()

            if cursor.rowcount > 0:
                return get_user_by_id(user_id)
            return None
    except Exception as e:
        logger.error(f"Failed to update user {user_id}: {e}")
        return None


def delete_user(user_id: int) -> bool:
    """
    Delete user (cascade deletes voice_profiles, refresh_tokens, and sets stories.user_id to NULL)

    Args:
        user_id: User ID to delete

    Returns:
        True if deleted, False otherwise
    """
    try:
        with get_db() as conn:
            cursor = get_cursor(conn)
            cursor.execute(_format_query("DELETE FROM users WHERE id = ?"), (user_id,))
            conn.commit()

            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Deleted user id={user_id}")
            return deleted
    except Exception as e:
        logger.error(f"Failed to delete user {user_id}: {e}")
        return False


def user_exists(username: Optional[str] = None, email: Optional[str] = None) -> bool:
    """
    Check if user exists by username or email

    Args:
        username: Username to check (optional)
        email: Email to check (optional)

    Returns:
        True if user exists, False otherwise
    """
    if username:
        return get_user_by_username(username) is not None
    if email:
        return get_user_by_email(email) is not None
    return False
