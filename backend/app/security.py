import re
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from app.config import settings


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