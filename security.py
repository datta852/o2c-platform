import os
import secrets

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(api_key: str | None = Depends(_api_key_header)) -> None:
    """Enforce an API key when configured; unset keys keep localhost demos simple."""
    expected = os.getenv("O2C_API_KEY")
    if expected and (not api_key or not secrets.compare_digest(api_key, expected)):
        raise HTTPException(status_code=401, detail="Valid X-API-Key header required")
