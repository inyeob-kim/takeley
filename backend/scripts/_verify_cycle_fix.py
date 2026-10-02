"""Force official module due + run one heavy cycle body; print health."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.db.models import DiscoveryModule, Signal
from app.db.session import SessionLocal, init_db
from worker.main import run_heavy_cycle_body


def main() -> None:
    init_db()
    db = SessionLocal()
    row = db.query(DiscoveryModule).filter(DiscoveryModule.id == "official").first()
    if row:
        row.last_finished_at = datetime.utcnow() - timedelta(days=1)
        row.last_status = "ok"
        db.commit()
        print("official forced due")

    stages = run_heavy_cycle_body(db)
    print("stages", stages)

    now = datetime.utcnow()
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    for kind in ("ISSUE", "NEWS"):
        pub = (
            db.query(Signal)
            .filter(
                Signal.content_kind == kind,
                Signal.status == "published",
                Signal.published_at >= day,
            )
            .count()
        )
        created = (
            db.query(Signal)
            .filter(Signal.content_kind == kind, Signal.first_seen_at >= day)
            .count()
        )
        drip = (
            db.query(Signal)
            .filter(
                Signal.content_kind == kind,
                Signal.status == "draft",
                Signal.scheduled_publish_at.isnot(None),
            )
            .count()
        )
        print(kind, "today_pub", pub, "today_created", created, "drip_queued", drip)
    db.close()
    print("OK")


if __name__ == "__main__":
    main()
