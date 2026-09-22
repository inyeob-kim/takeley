"""Admin auth — shared secret for the separate review portal."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def require_admin(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")) -> None:
    settings = get_settings()
    expected = (settings.admin_api_key or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API disabled (ADMIN_API_KEY not set)",
        )
    if not x_admin_key or x_admin_key.strip() != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin key",
        )
