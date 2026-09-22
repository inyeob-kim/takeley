"""One-shot wipe of issues / raw_items (+ related) for clean local retest."""

from sqlalchemy import text

from app.db.session import engine

TABLES = [
    "participations",
    "participation_options",
    "issue_comments",
    "issue_follows",
    "issue_views",
    "issue_user_events",
    "metric_snapshots",
    "signal_sources",
    "issues",
    "event_raw_items",
    "events",
    "raw_items",
]


def main() -> None:
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        existing = {
            r[0]
            for r in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
        }
        for table in TABLES:
            if table not in existing:
                print(f"{table}: (missing, skip)")
                continue
            before = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            conn.execute(text(f"DELETE FROM {table}"))
            after = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"{table}: {before} -> {after}")

        before_c = conn.execute(
            text(
                "SELECT COUNT(*) FROM ingest_cursors "
                "WHERE provider IN ('x', 'news')"
            )
        ).scalar()
        conn.execute(
            text("DELETE FROM ingest_cursors WHERE provider IN ('x', 'news')")
        )
        after_c = conn.execute(
            text(
                "SELECT COUNT(*) FROM ingest_cursors "
                "WHERE provider IN ('x', 'news')"
            )
        ).scalar()
        print(f"ingest_cursors(x,news): {before_c} -> {after_c}")
        conn.execute(text("PRAGMA foreign_keys=ON"))
    print("done")


if __name__ == "__main__":
    main()
