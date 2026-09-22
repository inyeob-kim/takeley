from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.repositories import UserRepository
from app.db.session import get_db
from app.schemas import UserSettingsOut, UserSettingsUpdateIn
from app.services.display_name import normalize_display_name
from app.services.preference_service import PreferenceService

router = APIRouter(prefix="/settings", tags=["settings"])


def _to_out(view, *, display_name: str | None = None) -> UserSettingsOut:
    return UserSettingsOut(
        user_id=view.user_id,
        brief_alarm_time=view.brief_alarm_time,
        timezone=view.timezone,
        notifications_enabled=view.notifications_enabled,
        tts_voice_gender=view.tts_voice_gender,
        display_name=display_name,
    )


def _load_display_name(db: Session, user_id: str) -> str | None:
    user = UserRepository(db).get_by_id(user_id)
    if not user:
        return None
    name = (user.display_name or "").strip()
    return name or None


@router.get("", response_model=UserSettingsOut)
def get_settings_api(
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> UserSettingsOut:
    uid = user_id or get_settings().default_user_id
    view = PreferenceService(db).get(uid)
    return _to_out(view, display_name=_load_display_name(db, uid))


@router.patch("", response_model=UserSettingsOut)
def patch_settings_api(
    body: UserSettingsUpdateIn,
    user_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> UserSettingsOut:
    uid = user_id or get_settings().default_user_id
    prefs = PreferenceService(db)
    try:
        view = prefs.upsert(
            uid,
            brief_alarm_time=body.brief_alarm_time,
            timezone=body.timezone,
            notifications_enabled=body.notifications_enabled,
            tts_voice_gender=body.tts_voice_gender,
        )
        if "display_name" in body.model_fields_set:
            name = normalize_display_name(body.display_name)
            UserRepository(db).set_display_name(uid, name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _to_out(view, display_name=_load_display_name(db, uid))
