from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.models import DeviceToken, PushNotification
from app.db.session import Base
from app.schemas import DeviceRegisterIn, PushDeviceRegisterIn
from app.services.device_service import DeviceService
from app.services.push_enqueue_service import (
    enqueue_signal_new,
)
from app.services.push_token_service import PushTokenService


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _user_with_token(db, device_id: str = "device-push-00001", platform: str = "ios"):
    user = DeviceService(db).register(
        DeviceRegisterIn(device_id=device_id, platform=platform)
    ).user
    PushTokenService(db).register(
        PushDeviceRegisterIn(
            user_id=user.id,
            fcm_token="x" * 40,
            platform=platform,
            client_device_id=device_id,
        )
    )
    return user


def test_push_token_register_upsert():
    db = _session()
    user = DeviceService(db).register(
        DeviceRegisterIn(device_id="device-tok-11111", platform="android")
    ).user
    svc = PushTokenService(db)
    first = svc.register(
        PushDeviceRegisterIn(
            user_id=user.id,
            fcm_token="fcm-token-aaaaaaaaaaaaaaaa",
            platform="android",
        )
    )
    second = svc.register(
        PushDeviceRegisterIn(
            user_id=user.id,
            fcm_token="fcm-token-aaaaaaaaaaaaaaaa",
            platform="android",
        )
    )
    assert first.created is True
    assert second.created is False
    assert db.query(DeviceToken).count() == 1


def test_enqueue_signal_new_broadcast_and_daily_cap(monkeypatch):
    db = _session()
    user = _user_with_token(db, device_id="device-sig-22222")
    # Second user without token — skipped_token, not enqueued.
    DeviceService(db).register(
        DeviceRegisterIn(device_id="device-no-token", platform="web")
    )

    settings = Settings(signal_push_daily_cap=2, mvp_asset_symbol="TSLA")
    monkeypatch.setattr(
        "app.services.push_enqueue_service.get_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "app.services.preference_service.get_settings",
        lambda: settings,
    )

    r1 = enqueue_signal_new(
        db,
        signal_id="sig-1",
        title="Issue one",
        summary="Demand rising",
        related_symbols=[],
    )
    assert r1["enqueued"] == 1
    assert r1["skipped_token"] >= 1

    r2 = enqueue_signal_new(
        db,
        signal_id="sig-2",
        title="Issue two",
        summary="More",
        related_symbols=["MU"],
    )
    assert r2["enqueued"] == 1

    r3 = enqueue_signal_new(
        db,
        signal_id="sig-3",
        title="Issue three",
        summary="Cap hit",
        related_symbols=[],
    )
    assert r3["enqueued"] == 0
    assert r3["skipped_cap"] == 1


def test_enqueue_signal_dedupe_same_signal():
    db = _session()
    user = _user_with_token(db, device_id="device-dedupe-333")

    first = enqueue_signal_new(
        db,
        signal_id="sig-same",
        title="Same",
        summary="Once",
        related_symbols=[],
    )
    second = enqueue_signal_new(
        db,
        signal_id="sig-same",
        title="Same",
        summary="Once",
        related_symbols=[],
    )
    assert first["enqueued"] == 1
    assert second["enqueued"] == 0
    assert second["skipped_dedupe"] == 1
