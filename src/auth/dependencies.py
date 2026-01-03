"""
FastAPI dependencies for authentication
"""
import logging
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .security import decode_token, validate_token_type
from ..database.user_service import get_user_by_id

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme for FastAPI
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    FastAPI dependency to get current authenticated user

    Usage:
        @router.get("/protected")
        async def protected_route(user: dict = Depends(get_current_user)):
            # user is a dict with id, username, email, etc.
            return {"message": f"Hello {user['username']}"}

    Args:
        credentials: HTTP Bearer token from Authorization header

    Returns:
        User dict if authenticated

    Raises:
        HTTPException: 401 if authentication fails
    """
    token = credentials.credentials

    # Decode token
    payload = decode_token(token)
    if not payload:
        logger.warning("Invalid or expired token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate it's an access token (not refresh token)
    if not validate_token_type(token, "access"):
        logger.warning("Token type mismatch: expected access token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user ID from token
    user_id = payload.get("sub")
    if not user_id:
        logger.error("Token missing 'sub' claim")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    user = get_user_by_id(int(user_id))
    if not user:
        logger.warning(f"User {user_id} not found in database")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        logger.warning(f"User {user_id} is inactive")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    logger.debug(f"User {user.username} authenticated successfully")

    # Return user as dict (exclude password hash)
    return user.to_dict(include_password=False)


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """
    FastAPI dependency to get current user if authenticated, None otherwise

    Useful for routes that work both with and without authentication.

    Usage:
        @router.get("/public-or-private")
        async def mixed_route(user: Optional[dict] = Depends(get_optional_user)):
            if user:
                return {"message": f"Hello {user['username']}"}
            return {"message": "Hello guest"}

    Args:
        credentials: Optional HTTP Bearer token

    Returns:
        User dict if authenticated, None if not
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


async def get_current_active_user(
    user: dict = Depends(get_current_user)
) -> dict:
    """
    Get current active user (alias for get_current_user for clarity)

    Args:
        user: User dict from get_current_user

    Returns:
        User dict if active

    Raises:
        HTTPException: 403 if user is inactive
    """
    # User is already checked for active status in get_current_user
    return user


async def get_current_verified_user(
    user: dict = Depends(get_current_user)
) -> dict:
    """
    Get current verified user (email verified)

    Args:
        user: User dict from get_current_user

    Returns:
        User dict if verified

    Raises:
        HTTPException: 403 if user is not verified
    """
    if not user.get("is_verified"):
        logger.warning(f"User {user['id']} is not verified")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required",
        )

    return user
