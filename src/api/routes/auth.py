"""
Authentication API Routes
"""
import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status

from ..models.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    UserResponse,
    ChangePasswordRequest,
    MessageResponse,
)
from ...auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    validate_token_type,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from ...auth.dependencies import get_current_user
from ...database.user_service import (
    create_user,
    get_user_by_username,
    get_user_by_email,
    user_exists,
    update_last_login,
    update_user,
)
from ...database.refresh_token_service import (
    create_refresh_token as store_refresh_token,
    is_token_valid,
    revoke_token,
    revoke_user_tokens,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest):
    """
    Register a new user

    Returns:
        JWT access and refresh tokens
    """
    logger.info(f"Registration attempt for username: {request.username}, email: {request.email}")

    # Check if username already exists
    if user_exists(username=request.username):
        logger.warning(f"Registration failed - Username already exists: {request.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    # Check if email already exists
    if user_exists(email=request.email):
        logger.warning(f"Registration failed - Email already exists: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    try:
        # Hash password
        logger.debug(f"Hashing password for user: {request.username}")
        password_hash = hash_password(request.password)

        # Create user
        logger.debug(f"Creating user record for: {request.username}")
        user = create_user(
            username=request.username,
            email=request.email,
            password_hash=password_hash,
        )

        if not user:
            logger.error(f"Failed to create user in database: {request.username}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user",
            )

        logger.info(f"User created successfully: {user.username} (id={user.id})")

        # Create tokens
        logger.debug(f"Generating tokens for user: {user.username}")
        token_data = {"sub": str(user.id), "username": user.username}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        # Store refresh token in database
        logger.debug(f"Storing refresh token for user: {user.username}")
        store_refresh_token(user.id, refresh_token)

        logger.info(f"Registration completed successfully for user: {user.username}")
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    except Exception as e:
        logger.error(f"Registration error for {request.username}: {str(e)}", exc_info=True)
        raise


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    Login with username/email and password

    Returns:
        JWT access and refresh tokens
    """
    logger.info(f"Login attempt for: {request.username}")

    try:
        # Get user (try username first, then email)
        logger.debug(f"Looking up user: {request.username}")
        user = get_user_by_username(request.username)
        if not user:
            logger.debug(f"Username not found, trying email: {request.username}")
            user = get_user_by_email(request.username)

        if not user:
            logger.warning(f"Login failed - User not found: {request.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
            )

        logger.debug(f"User found: {user.username} (id={user.id})")

        # Verify password
        logger.debug(f"Verifying password for user: {user.username}")
        if not verify_password(request.password, user.password_hash):
            logger.warning(f"Login failed - Invalid password for user: {user.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
            )

        # Check if user is active
        if not user.is_active:
            logger.warning(f"Login failed - Inactive user login attempt: {user.username}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        # Update last login
        logger.debug(f"Updating last login for user: {user.username}")
        update_last_login(user.id)

        logger.info(f"User logged in successfully: {user.username} (id={user.id})")

        # Create tokens
        logger.debug(f"Generating tokens for user: {user.username}")
        token_data = {"sub": str(user.id), "username": user.username}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        # Store refresh token in database
        logger.debug(f"Storing refresh token for user: {user.username}")
        store_refresh_token(user.id, refresh_token)

        logger.info(f"Login completed successfully for user: {user.username}")
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error for {request.username}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login",
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: RefreshTokenRequest):
    """
    Refresh access token using refresh token

    Returns:
        New JWT access and refresh tokens
    """
    logger.debug("Token refresh request received")

    # Validate refresh token
    if not is_token_valid(request.refresh_token):
        logger.warning("Invalid or expired refresh token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Decode token
    payload = decode_token(request.refresh_token)
    if not payload:
        logger.error("Failed to decode refresh token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Validate token type
    if not validate_token_type(request.refresh_token, "refresh"):
        logger.warning("Token type mismatch: expected refresh token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    username = payload.get("username")

    # Revoke old refresh token
    revoke_token(request.refresh_token)

    # Create new tokens
    token_data = {"sub": user_id, "username": username}
    access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)

    # Store new refresh token
    store_refresh_token(int(user_id), new_refresh_token)

    logger.info(f"Token refreshed successfully for user: {username}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: RefreshTokenRequest,
    user: dict = Depends(get_current_user),
):
    """
    Logout user by revoking refresh token

    Requires:
        - Valid access token in Authorization header
        - Refresh token in request body
    """
    logger.info(f"Logout request for user: {user['username']}")

    # Revoke the refresh token
    if revoke_token(request.refresh_token):
        logger.info(f"User logged out successfully: {user['username']}")
        return MessageResponse(message="Logged out successfully")
    else:
        logger.warning(f"Failed to revoke token for user: {user['username']}")
        return MessageResponse(
            message="Logged out",
            detail="Token was already revoked or invalid",
        )


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(user: dict = Depends(get_current_user)):
    """
    Logout from all devices by revoking all refresh tokens

    Requires:
        - Valid access token in Authorization header
    """
    logger.info(f"Logout all request for user: {user['username']}")

    count = revoke_user_tokens(user["id"])
    logger.info(f"Revoked {count} tokens for user: {user['username']}")

    return MessageResponse(
        message="Logged out from all devices",
        detail=f"Revoked {count} refresh token(s)",
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    """
    Get current user information

    Requires:
        - Valid access token in Authorization header

    Returns:
        Current user profile
    """
    logger.debug(f"Get user info request: {user['username']}")

    return UserResponse(
        id=user["id"],
        username=user["username"],
        email=user["email"],
        is_active=user["is_active"],
        is_verified=user["is_verified"],
        created_at=user["created_at"],
        last_login=user.get("last_login"),
    )


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    request: ChangePasswordRequest,
    user: dict = Depends(get_current_user),
):
    """
    Change user password

    Requires:
        - Valid access token in Authorization header
        - Current password
        - New password

    Returns:
        Success message
    """
    logger.info(f"Password change request for user: {user['username']}")

    # Get user with password hash
    from ...database.user_service import get_user_by_id

    full_user = get_user_by_id(user["id"])
    if not full_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify current password
    if not verify_password(request.current_password, full_user.password_hash):
        logger.warning(f"Invalid current password for user: {user['username']}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Hash new password
    new_password_hash = hash_password(request.new_password)

    # Update password
    updated_user = update_user(user["id"], password_hash=new_password_hash)
    if not updated_user:
        logger.error(f"Failed to update password for user: {user['username']}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password",
        )

    # Revoke all existing refresh tokens (force re-login on all devices)
    revoke_user_tokens(user["id"])

    logger.info(f"Password changed successfully for user: {user['username']}")

    return MessageResponse(
        message="Password changed successfully",
        detail="Please login again on all devices",
    )
