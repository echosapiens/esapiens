"""Auth router — JWT login, ORCID OAuth callback, current-user endpoint."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Helpers ──────────────────────────────────────────────────────────

def _create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Sign a JWT access token."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def _get_current_user_id(token: str) -> uuid.UUID:
    """Decode a JWT and return the subject (user id)."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise JWTError("missing sub")
        return uuid.UUID(user_id)
    except (JWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ── Dependency ────────────────────────────────────────────────────────

async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str, Depends(_token_from_header)],
) -> uuid.UUID:
    """FastAPI dependency that extracts and validates the current user from the Authorization header."""
    return await _get_current_user_id(token)


async def _token_from_header() -> str:
    """Placeholder — FastAPI security utility extracts bearer token."""
    # In production you would use:
    #   from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    #   creds: HTTPAuthorizationCredentials = Depends(HTTPBearer())
    # For now we keep it simple for the stub.
    raise HTTPException(status_code=401, detail="Not implemented — use OAuth2PasswordBearer")


# ── Request / Response schemas ───────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    id: uuid.UUID
    email: str | None = None
    orcid: str | None = None


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    """Authenticate a user and return a JWT.

    NOTE: This is a simplified stub — in production you would verify
    credentials against the users table with hashed passwords.
    """
    # Stub: accept any credentials and issue a token for a deterministic user id.
    # Replace with real password verification before production.
    fake_user_id = uuid.uuid5(uuid.NAMESPACE_DNS, body.email)
    token = _create_access_token(str(fake_user_id))
    return TokenResponse(access_token=token)


@router.post("/dev-login", response_model=TokenResponse)
async def dev_login() -> TokenResponse:
    """Dev-only: return a JWT for the seeded dev user.

    This endpoint is disabled when SECRET_KEY != 'change-me-in-production'.
    """
    if settings.SECRET_KEY != "change-me-in-production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dev login is only available in development",
        )
    dev_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    token = _create_access_token(str(dev_user_id))
    return TokenResponse(access_token=token)


@router.post("/orcid/callback", response_model=TokenResponse)
async def orcid_callback(code: str) -> TokenResponse:
    """Exchange an ORCID OAuth authorization code for an access token.

    NOTE: This is a stub — implement the full ORCID OAuth2 flow before production.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://orcid.org/oauth/token",
            data={
                "client_id": settings.ORCID_CLIENT_ID,
                "client_secret": settings.ORCID_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.ORCID_REDIRECT_URI,
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="ORCID auth failed")

    orcid_data = resp.json()
    orcid_id: str = orcid_data.get("orcid", "")
    user_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"orcid:{orcid_id}")
    token = _create_access_token(str(user_id))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserInfo)
async def me(current_user: Annotated[uuid.UUID, Depends(get_current_user)]) -> UserInfo:
    """Return info about the currently authenticated user."""
    return UserInfo(id=current_user)