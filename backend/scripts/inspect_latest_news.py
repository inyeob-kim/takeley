"""Inspect latest NEWS card and its raw source text."""

from sqlalchemy import text

from app.db.session import SessionLocal

db = SessionLocal()
issue = db.execute(
    text(
        """
        SELECT id::text, title, summary, key_points::text,
               left(coalesce(column_body, ''), 200) AS column_body,
               status, content_kind
        FROM issues
        WHERE content_kind = 'NEWS'
        ORDER BY first_seen_at DESC NULLS LAST
        LIMIT 1
        """
    )
).mappings().first()
print("=== issue ===")
for k, v in dict(issue or {}).items():
    print(f"{k}: {v}")

if issue:
    srcs = db.execute(
        text(
            """
            SELECT ss.url, ss.title, ss.provider, ss.raw_item_id::text,
                   left(coalesce(r.title, ''), 200) AS raw_title,
                   left(coalesce(r.text, ''), 1200) AS raw_text
            FROM signal_sources ss
            LEFT JOIN raw_items r ON r.id = ss.raw_item_id
            WHERE ss.signal_id = :sid
            """
        ),
        {"sid": issue["id"]},
    ).mappings().all()
    print("=== sources / raw ===")
    for s in srcs:
        for k, v in dict(s).items():
            print(f"{k}: {v}")
        print("---")

db.close()
