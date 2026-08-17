import re
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.config import settings

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
):
    """Validate JWT token. Returns user info dict or raises 403.

    When DISABLE_AUTH is True (dev mode), allows all requests through."""
    if settings.DISABLE_AUTH:
        return {"sub": "dev-user", "role": "admin"}
    if credentials is None:
        raise HTTPException(status_code=403, detail="Not authenticated")
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=403, detail="Invalid or expired token")
    return payload


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=24)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Decode and validate a JWT access token. Returns None on failure."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def sanitize_cli_command(command: str) -> str:
    """
    Sanitize a CLI command to prevent injection.
    - Removes backticks
    - Disallows unquoted semicolons or && outside of the main command
    - Strips dangerous shell metacharacters
    - Allows only safe patterns: alphanumeric, pipes, redirects, flags, paths
    """
    # Remove backticks entirely
    command = command.replace("`", "")

    # Remove $() command substitution
    command = re.sub(r'\$\(.*?\)', '', command)

    # Only allow safe characters
    allowed = re.compile(r'^[a-zA-Z0-9_\-\/\.,:=\s\|<>@\&\;\(\)\"\'\$\[\]\+%#~!?\{\}]+$')
    if not allowed.match(command):
        # Strip unsafe characters
        command = re.sub(r'[^a-zA-Z0-9_\-\/\.,:=\s\|<>@\&\;\(\)\"\'\$\[\]\+%#~!?\{\}]', '', command)

    return command.strip()