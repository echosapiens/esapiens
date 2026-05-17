"""
Authentication Module — JWT-based user auth for E.sapiens.

Provides:
  - User model & SQLite-backed user store
  - Password hashing with bcrypt (direct, not passlib)
  - JWT access token creation / verification
  - FastAPI dependency `get_current_user` for route protection
  - Registration & login endpoints
"""

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field

from storage import get_storage

# ═══════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_SECONDS = int(os.environ.get("JWT_EXPIRATION_SECONDS", 604800))  # 7 days

security_scheme = HTTPBearer()

auth_router = APIRouter(prefix="/auth", tags=["auth"])

# ═══════════════════════════════════════════════════════════════════════════
# Pydantic Schemas
# ═══════════════════════════════════════════════════════════════════════════


class UserCreate(BaseModel):
    """Registration request body."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field("", max_length=128)


class UserLogin(BaseModel):
    """Login request body."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """User data returned in API responses (no password)."""
    id: str
    email: str
    full_name: str
    created_at: str


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ═══════════════════════════════════════════════════════════════════════════
# User table schema (added to the same esapiens.db)
# ═══════════════════════════════════════════════════════════════════════════

TABLE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    email       TEXT NOT NULL UNIQUE,
    full_name   TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    created_at  REAL NOT NULL
);
"""

INDEX_USERS_EMAIL = """
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
"""


def _ensure_users_table() -> None:
    """Create users table if it doesn't exist yet."""
    storage = get_storage()
    storage.conn.executescript(TABLE_USERS)
    storage.conn.execute(INDEX_USERS_EMAIL)
    storage.conn.commit()


# ═══════════════════════════════════════════════════════════════════════════
# Password hashing (bcrypt direct — no passlib dependency)
# ═══════════════════════════════════════════════════════════════════════════


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt. Returns the hash as a string."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


# ═══════════════════════════════════════════════════════════════════════════
# JWT token helpers
# ═══════════════════════════════════════════════════════════════════════════


def create_access_token(user_id: str, email: str) -> str:
    """Create a signed JWT access token for the given user."""
    now = time.time()
    payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + JWT_EXPIRATION_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode & validate a JWT token. Returns payload dict or None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


# ═══════════════════════════════════════════════════════════════════════════
# User CRUD
# ═══════════════════════════════════════════════════════════════════════════


def create_user(email: str, password: str, full_name: str = "") -> dict:
    """
    Register a new user. Raises HTTPException(409) if email already exists.
    Returns user dict (no password).
    """
    _ensure_users_table()
    storage = get_storage()

    # Check if email already taken
    cursor = storage.conn.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cursor.fetchone() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    user_id = f"usr_{uuid.uuid4().hex[:12]}"
    now = time.time()
    hashed = hash_password(password)

    storage.conn.execute(
        """INSERT INTO users (id, email, full_name, password_hash, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, email, full_name, hashed, now),
    )
    storage.conn.commit()

    # Also create a user workspace profile
    storage.create_user_profile(user_id)

    return {
        "id": user_id,
        "email": email,
        "full_name": full_name,
        "created_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
    }


def authenticate_user(email: str, password: str) -> Optional[dict]:
    """
    Verify credentials. Returns user dict (no password) on success, None otherwise.
    """
    _ensure_users_table()
    storage = get_storage()

    cursor = storage.conn.execute(
        "SELECT id, email, full_name, password_hash, created_at FROM users WHERE email = ?",
        (email,),
    )
    row = cursor.fetchone()
    if row is None:
        return None

    if not verify_password(password, row["password_hash"]):
        return None

    return {
        "id": row["id"],
        "email": row["email"],
        "full_name": row["full_name"],
        "created_at": datetime.fromtimestamp(row["created_at"], tz=timezone.utc).isoformat(),
    }


def get_user_by_id(user_id: str) -> Optional[dict]:
    """Look up a user by ID. Returns user dict or None."""
    _ensure_users_table()
    storage = get_storage()

    cursor = storage.conn.execute(
        "SELECT id, email, full_name, created_at FROM users WHERE id = ?",
        (user_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None

    return {
        "id": row["id"],
        "email": row["email"],
        "full_name": row["full_name"],
        "created_at": datetime.fromtimestamp(row["created_at"], tz=timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════════════
# FastAPI dependency — get current user from JWT
# ═══════════════════════════════════════════════════════════════════════════


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> dict:
    """
    FastAPI dependency that extracts the Bearer token from the Authorization
    header, validates it, and returns the user dict.

    Raises 401 if the token is missing, invalid, or expired.
    Raises 404 if the user no longer exists.
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str = payload.get("sub", "")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# ═══════════════════════════════════════════════════════════════════════════
# Auth routes
# ═══════════════════════════════════════════════════════════════════════════


@auth_router.post("/register", response_model=TokenResponse)
async def register(body: UserCreate) -> dict:
    """Register a new user and return a JWT token."""
    user = create_user(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
    )
    token = create_access_token(user["id"], user["email"])
    return TokenResponse(
        access_token=token,
        user=UserResponse(**user),
    )


@auth_router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin) -> dict:
    """Authenticate an existing user and return a JWT token."""
    user = authenticate_user(body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(user["id"], user["email"])
    return TokenResponse(
        access_token=token,
        user=UserResponse(**user),
    )


@auth_router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)) -> dict:
    """Return the authenticated user's profile."""
    return UserResponse(**{
        "id": current_user["id"],
        "email": current_user["email"],
        "full_name": current_user["full_name"],
        "created_at": current_user["created_at"],
    })