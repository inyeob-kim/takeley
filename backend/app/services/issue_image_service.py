"""Persist Issue cover images under local storage (admin upload)."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings

_ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

_MEDIA_PREFIX = "/media/issue-images"


def issue_image_dir() -> Path:
    settings = get_settings()
    path = Path(settings.issue_image_dir)
    if not path.is_absolute():
        # Resolve relative to backend/ cwd when running uvicorn from backend/
        path = Path.cwd() / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def normalize_image_url(raw: str | None) -> str | None:
    """Validate / normalize image URL. Empty → clear (None)."""
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    if text.startswith(_MEDIA_PREFIX + "/") or text.startswith(_MEDIA_PREFIX + "?"):
        return text.split("?", 1)[0]
    if text.startswith("http://") or text.startswith("https://"):
        if len(text) > 1024:
            raise ValueError("image_url_too_long")
        return text
    raise ValueError("invalid_image_url")


async def save_issue_image(file: UploadFile) -> str:
    """Write upload to disk; return public path under /media/issue-images/."""
    settings = get_settings()
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    ext = _ALLOWED_TYPES.get(content_type)
    if not ext:
        # Fallback from filename
        name = (file.filename or "").lower()
        for candidate, e in ((".jpg", ".jpg"), (".jpeg", ".jpg"), (".png", ".png"), (".webp", ".webp"), (".gif", ".gif")):
            if name.endswith(candidate):
                ext = e
                break
    if not ext:
        raise ValueError("unsupported_image_type")

    data = await file.read()
    if not data:
        raise ValueError("empty_image")
    if len(data) > int(settings.issue_image_max_bytes):
        raise ValueError("image_too_large")

    fname = f"{uuid.uuid4().hex}{ext}"
    dest = issue_image_dir() / fname
    dest.write_bytes(data)
    return f"{_MEDIA_PREFIX}/{fname}"


def delete_local_image_if_owned(image_url: str | None) -> None:
    """Best-effort delete when replacing/clearing an uploaded file."""
    if not image_url:
        return
    text = image_url.strip()
    if not text.startswith(_MEDIA_PREFIX + "/"):
        return
    name = text.rsplit("/", 1)[-1]
    if not re.fullmatch(r"[a-f0-9]{32}\.(jpg|png|webp|gif)", name):
        return
    path = issue_image_dir() / name
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            pass
