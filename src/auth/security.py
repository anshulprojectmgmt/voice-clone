"""
Security utilities for JWT authentication and password hashing
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import jwt
from passlib.context import CryptContext
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Password hashing context with bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt

    Bcrypt has a maximum password length of 72 bytes. We truncate the password
    to 72 bytes to avoid errors, as recommended by bcrypt documentation.

    Args:
        password: Plain text password

    Returns:
        Bcrypt hashed password
    """
    # Convert to bytes to properly truncate at 72 bytes boundary
    password_bytes = password.encode('utf-8')

    # Bcrypt can only handle passwords up to 72 bytes
    if len(password_bytes) > 72:
        logger.warning(f"Password length ({len(password_bytes)} bytes) exceeds bcrypt limit of 72 bytes, truncating")
        password_bytes = password_bytes[:72]
        password = password_bytes.decode('utf-8', errors='ignore')

    hashed = pwd_context.hash(password)
    logger.debug("Password hashed successfully")
    return hashed


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash

    Bcrypt has a maximum password length of 72 bytes. We truncate the password
    to 72 bytes for verification, matching the behavior in hash_password.

    Args:
        plain_password: Plain text password
        hashed_password: Bcrypt hashed password

    Returns:
        True if password matches, False otherwise
    """
    # Convert to bytes to properly truncate at 72 bytes boundary
    password_bytes = plain_password.encode('utf-8')

    # Bcrypt can only handle passwords up to 72 bytes
    if len(password_bytes) > 72:
        logger.debug(f"Password length ({len(password_bytes)} bytes) exceeds bcrypt limit, truncating for verification")
        password_bytes = password_bytes[:72]
        plain_password = password_bytes.decode('utf-8', errors='ignore')

    is_valid = pwd_context.verify(plain_password, hashed_password)
    if is_valid:
        logger.debug("Password verification successful")
    else:
        logger.warning("Password verification failed")
    return is_valid


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token

    Args:
        data: Payload data to encode (should include 'sub' for user ID)
        expires_delta: Optional custom expiration time

    Returns:
        JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "type": "access"})

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    logger.debug(f"Access token created, expires at {expire}")
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT refresh token

    Args:
        data: Payload data to encode (should include 'sub' for user ID)
        expires_delta: Optional custom expiration time

    Returns:
        JWT refresh token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({"exp": expire, "type": "refresh"})

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    logger.debug(f"Refresh token created, expires at {expire}")
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate JWT token

    Args:
        token: JWT token string

    Returns:
        Decoded payload if valid, None if invalid/expired
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        logger.debug("Token decoded successfully")
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        return None
    except jwt.JWTError as e:
        logger.error(f"JWT decode error: {e}")
        return None


def get_token_expiry(token: str) -> Optional[datetime]:
    """
    Get expiration time from token

    Args:
        token: JWT token string

    Returns:
        Expiration datetime if valid, None otherwise
    """
    payload = decode_token(token)
    if payload and "exp" in payload:
        return datetime.fromtimestamp(payload["exp"])
    return None


def is_token_expired(token: str) -> bool:
    """
    Check if token is expired

    Args:
        token: JWT token string

    Returns:
        True if expired, False otherwise
    """
    expiry = get_token_expiry(token)
    if expiry:
        return datetime.utcnow() > expiry
    return True


def validate_token_type(token: str, expected_type: str) -> bool:
    """
    Validate token type (access or refresh)

    Args:
        token: JWT token string
        expected_type: Expected type ("access" or "refresh")

    Returns:
        True if token type matches, False otherwise
    """
    payload = decode_token(token)
    if payload and payload.get("type") == expected_type:
        return True

    logger.warning(f"Token type mismatch: expected {expected_type}, got {payload.get('type') if payload else None}")
    return False
