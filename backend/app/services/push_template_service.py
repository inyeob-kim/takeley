"""Push notification copy templates (DB-managed)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import PushNotificationTemplate

# Built-in fallbacks if DB row missing.
# signal_new: {title}/{body} are pre-built by push_copy (never raw summary).
DEFAULT_TEMPLATES: dict[str, tuple[str, str]] = {
    "signal_new": (
        "{title}",
        "{body}",
    ),
    "issue_update": (
        "내가 팔로우한 이슈에 새로운 소식이 추가됐어요.",
        "{title}",
    ),
}

# Legacy rows seeded with {summary} — migrate to re-engagement body placeholder.
_LEGACY_SIGNAL_NEW_BODY = "{summary}"
_REENGAGE_SIGNAL_NEW_BODY = "{body}"


def render_template(template: str, values: dict[str, str]) -> str:
    """Replace {key} placeholders. Unknown keys left as-is."""
    out = template or ""
    for key, value in values.items():
        out = out.replace("{" + key + "}", value if value is not None else "")
    return out.strip()


def ensure_default_templates(db: Session) -> int:
    """Insert missing default templates. Returns number created."""
    created = 0
    for category, (title, body) in DEFAULT_TEMPLATES.items():
        exists = (
            db.query(PushNotificationTemplate.id)
            .filter(
                PushNotificationTemplate.category == category,
                PushNotificationTemplate.locale == "ko",
            )
            .first()
        )
        if exists:
            continue
        db.add(
            PushNotificationTemplate(
                category=category,
                locale="ko",
                title_template=title,
                body_template=body,
                is_active=True,
            )
        )
        created += 1

    # Soft migrate only the original default seed (not admin-customized templates).
    legacy = (
        db.query(PushNotificationTemplate)
        .filter(
            PushNotificationTemplate.category == "signal_new",
            PushNotificationTemplate.locale == "ko",
            PushNotificationTemplate.title_template == "{title}",
            PushNotificationTemplate.body_template == _LEGACY_SIGNAL_NEW_BODY,
        )
        .one_or_none()
    )
    if legacy:
        legacy.body_template = _REENGAGE_SIGNAL_NEW_BODY
        legacy.updated_at = datetime.utcnow()
        created += 1

    if created:
        db.commit()
    return created


def get_active_template(
    db: Session,
    category: str,
    *,
    locale: str = "ko",
) -> tuple[str, str]:
    """Return (title_template, body_template); falls back to defaults."""
    ensure_default_templates(db)
    row = (
        db.query(PushNotificationTemplate)
        .filter(
            PushNotificationTemplate.category == category,
            PushNotificationTemplate.locale == locale,
            PushNotificationTemplate.is_active.is_(True),
        )
        .one_or_none()
    )
    if row:
        return row.title_template, row.body_template
    return DEFAULT_TEMPLATES.get(category, ("TAKELEY", ""))


def list_templates(db: Session) -> list[PushNotificationTemplate]:
    ensure_default_templates(db)
    return (
        db.query(PushNotificationTemplate)
        .order_by(PushNotificationTemplate.category.asc())
        .all()
    )


def update_template(
    db: Session,
    category: str,
    *,
    title_template: str | None = None,
    body_template: str | None = None,
    is_active: bool | None = None,
    locale: str = "ko",
) -> PushNotificationTemplate:
    ensure_default_templates(db)
    row = (
        db.query(PushNotificationTemplate)
        .filter(
            PushNotificationTemplate.category == category,
            PushNotificationTemplate.locale == locale,
        )
        .one_or_none()
    )
    if not row:
        raise ValueError(f"unknown template category: {category}")
    if title_template is not None:
        text = title_template.strip()
        if not text:
            raise ValueError("title_template required")
        row.title_template = text[:200]
    if body_template is not None:
        text = body_template.strip()
        if not text:
            raise ValueError("body_template required")
        row.body_template = text
    if is_active is not None:
        row.is_active = bool(is_active)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def render_push_copy(
    db: Session,
    category: str,
    values: dict[str, str],
    *,
    title_limit: int = 80,
    body_limit: int = 120,
) -> tuple[str, str]:
    title_t, body_t = get_active_template(db, category)
    title = render_template(title_t, values)
    body = render_template(body_t, values)
    if len(title) > title_limit:
        title = title[: title_limit - 1].rstrip() + "…"
    if len(body) > body_limit:
        body = body[: body_limit - 1].rstrip() + "…"
    if not title:
        title = "TAKELEY"
    if not body:
        body = title
    return title, body
