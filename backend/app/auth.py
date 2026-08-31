import secrets

from fastapi import Header, HTTPException, status
from .config import get_settings


async def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.admin_token or settings.admin_token == "change-me":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin authentication is not configured",
        )
    if not x_admin_token or not secrets.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token",
            headers={"WWW-Authenticate": "AdminToken"},
        )
