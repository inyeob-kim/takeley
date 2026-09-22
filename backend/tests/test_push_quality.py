"""Push enqueue uses re-engagement copy (not Issue summary)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.models import Asset, WatchlistItem
from app.db.session import Base
from app.schemas import DeviceRegisterIn, PushDeviceRegisterIn
from app.services.device_service import DeviceService
from app.services.push_enqueue_service import enqueue_signal_new
from app.services.push_token_service import PushTokenService


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _user_with_token(db):
    user = DeviceService(db).register(
        DeviceRegisterIn(device_id="device-quality-0001", platform="ios")
    ).user
    PushTokenService(db).register(
        PushDeviceRegisterIn(
            user_id=user.id,
            fcm_token="y" * 40,
            platform="ios",
            client_device_id="device-quality-0001",
        )
    )
    asset = Asset(symbol="TSLA", name="Tesla", name_ko="테슬라", kind="asset")
    db.add(asset)
    db.commit()
    db.refresh(asset)
    db.add(WatchlistItem(user_id=user.id, asset_id=asset.id))
    db.commit()
    return user


def test_enqueue_body_excludes_summary(monkeypatch):
    db = _session()
    _user_with_token(db)
    settings = Settings(signal_push_daily_cap=5, mvp_asset_symbol="TSLA")
    monkeypatch.setattr(
        "app.services.push_enqueue_service.get_settings", lambda: settings
    )
    monkeypatch.setattr(
        "app.services.preference_service.get_settings", lambda: settings
    )

    summary = (
        "최근 빅테크 기업들 간의 경쟁이 치열해지고 있어요. "
        "하지만 시장 점유율 차트가 공개되면 상황이 달라질 수 있다는 의견이 많아요."
    )
    result = enqueue_signal_new(
        db,
        signal_id="sig-copy-1",
        title="빅테크 경쟁",
        summary=summary,
        related_symbols=["TSLA"],
        participation_suitable=False,
        trend_status="NORMAL",
    )
    assert result["enqueued"] == 1
    assert result["push_kind"] == "general"

    from app.db.models import PushNotification

    row = db.query(PushNotification).one()
    assert summary not in (row.body or "")
    assert "확인" in (row.body or "")
    assert row.data.get("push_kind") == "general"
    assert row.data.get("issue_id") == "sig-copy-1"
    assert row.data.get("route") == "/issues/sig-copy-1"
