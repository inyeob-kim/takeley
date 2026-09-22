from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import SubscriptionPayment
from app.db.session import Base
from app.schemas import DeviceRegisterIn
from app.services.device_service import DeviceService
from app.services.entitlement_service import EntitlementService


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_device_register_is_idempotent():
    db = _session()
    svc = DeviceService(db)
    first = svc.register(
        DeviceRegisterIn(device_id="device-abc-12345", platform="ios")
    )
    second = svc.register(
        DeviceRegisterIn(device_id="device-abc-12345", platform="ios")
    )
    assert first.created is True
    assert second.created is False
    assert first.user.id == second.user.id
    assert first.user.plan_type == "FREE"
    assert first.user.is_pro is False


def test_paid_subscription_makes_pro():
    db = _session()
    user = DeviceService(db).register(
        DeviceRegisterIn(device_id="device-pro-99999", platform="android")
    ).user

    db.add(
        SubscriptionPayment(
            user_id=user.id,
            transaction_id="txn-1",
            platform="android",
            amount=4900,
            currency="KRW",
            payment_status="PAID",
            expires_at=datetime.utcnow() + timedelta(days=30),
            product_id="market_radar.pro.monthly",
        )
    )
    db.commit()

    ent = EntitlementService(db).entitlements_for_user(user.id)
    assert ent.pro is True
    assert ent.plan_type == "PRO"
    assert ent.plan_expire_at is not None


def test_expired_subscription_is_free():
    db = _session()
    user = DeviceService(db).register(
        DeviceRegisterIn(device_id="device-expired-1", platform="web")
    ).user
    db.add(
        SubscriptionPayment(
            user_id=user.id,
            transaction_id="txn-old",
            platform="ios",
            payment_status="PAID",
            expires_at=datetime.utcnow() - timedelta(days=1),
            product_id="market_radar.pro.monthly",
        )
    )
    db.commit()
    ent = EntitlementService(db).entitlements_for_user(user.id)
    assert ent.pro is False
    assert ent.plan_type == "FREE"
