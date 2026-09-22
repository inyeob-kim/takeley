"""User preference helpers (brief alarm schedule, TTS voice)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import UserPreference

_ALARM_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")

# Product-facing gender → OpenAI TTS voice id.
_TTS_GENDER_VOICES = {
    "female": "nova",
    "male": "onyx",
}


def parse_alarm_time(value: str) -> time:
    raw = (value or "").strip()
    match = _ALARM_RE.match(raw)
    if not match:
        raise ValueError("brief_alarm_time must be HH:MM (24h)")
    return time(hour=int(match.group(1)), minute=int(match.group(2)))


def normalize_alarm_time(value: str) -> str:
    t = parse_alarm_time(value)
    return f"{t.hour:02d}:{t.minute:02d}"


def normalize_tts_voice_gender(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw in ("female", "f", "woman", "여자"):
        return "female"
    if raw in ("male", "m", "man", "남자"):
        return "male"
    raise ValueError("tts_voice_gender must be female or male")


def resolve_tts_voice(gender: str | None) -> str:
    """Map preference gender to OpenAI voice; fall back to settings.tts_voice."""
    try:
        key = normalize_tts_voice_gender(gender)
    except ValueError:
        key = "female"
    mapped = _TTS_GENDER_VOICES.get(key)
    if mapped:
        return mapped
    return get_settings().tts_voice or "nova"


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo(get_settings().default_timezone)


@dataclass(frozen=True)
class PreferenceView:
    user_id: str
    brief_alarm_time: str
    timezone: str
    notifications_enabled: bool
    tts_voice_gender: str = "female"


class PreferenceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def get(self, user_id: str) -> PreferenceView:
        row = (
            self.db.query(UserPreference)
            .filter(UserPreference.user_id == user_id)
            .one_or_none()
        )
        if not row:
            return PreferenceView(
                user_id=user_id,
                brief_alarm_time=self.settings.default_brief_alarm_time,
                timezone=self.settings.default_timezone,
                notifications_enabled=True,
                tts_voice_gender=self.settings.default_tts_voice_gender,
            )
        gender = getattr(row, "tts_voice_gender", None) or self.settings.default_tts_voice_gender
        try:
            gender = normalize_tts_voice_gender(gender)
        except ValueError:
            gender = self.settings.default_tts_voice_gender
        return PreferenceView(
            user_id=row.user_id,
            brief_alarm_time=row.brief_alarm_time
            or self.settings.default_brief_alarm_time,
            timezone=row.timezone or self.settings.default_timezone,
            notifications_enabled=bool(row.notifications_enabled),
            tts_voice_gender=gender,
        )

    def upsert(
        self,
        user_id: str,
        *,
        brief_alarm_time: str | None = None,
        timezone: str | None = None,
        notifications_enabled: bool | None = None,
        tts_voice_gender: str | None = None,
    ) -> PreferenceView:
        current = self.get(user_id)
        alarm = (
            normalize_alarm_time(brief_alarm_time)
            if brief_alarm_time is not None
            else current.brief_alarm_time
        )
        tz = (timezone or current.timezone).strip() or self.settings.default_timezone
        # Validate timezone name early.
        _zone(tz)
        notif = (
            current.notifications_enabled
            if notifications_enabled is None
            else bool(notifications_enabled)
        )
        gender = (
            normalize_tts_voice_gender(tts_voice_gender)
            if tts_voice_gender is not None
            else current.tts_voice_gender
        )

        row = (
            self.db.query(UserPreference)
            .filter(UserPreference.user_id == user_id)
            .one_or_none()
        )
        if row:
            row.brief_alarm_time = alarm
            row.timezone = tz
            row.notifications_enabled = notif
            row.tts_voice_gender = gender
            row.updated_at = datetime.utcnow()
        else:
            row = UserPreference(
                user_id=user_id,
                brief_alarm_time=alarm,
                timezone=tz,
                notifications_enabled=notif,
                tts_voice_gender=gender,
            )
            self.db.add(row)
        self.db.commit()
        return self.get(user_id)

    def local_now(self, user_id: str) -> datetime:
        prefs = self.get(user_id)
        return datetime.now(_zone(prefs.timezone))

    def local_brief_date(self, user_id: str) -> str:
        return self.local_now(user_id).strftime("%Y-%m-%d")

    def is_brief_alarm_due(self, user_id: str) -> bool:
        """True when local time is at/after the user's briefing alarm today."""
        prefs = self.get(user_id)
        now = self.local_now(user_id)
        alarm = parse_alarm_time(prefs.brief_alarm_time)
        return (now.hour, now.minute) >= (alarm.hour, alarm.minute)
