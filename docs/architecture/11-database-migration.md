# 11 — Database Migration (TAKELEY)

## Principles

- Additive migrations first; one breaking rename documented below  
- Do not drop participation / follow / comment data  
- Alembic under `backend/alembic/versions/`; SQLite via `init_db` + rename patch

---

## Current Issue-relevant schema

- `raw_items`, `events`, `event_raw_items`
- **`issues`** (ex-`signals`) + Issue columns, counters, `content_updated_at`
- `signal_sources` (FK → `issues.id`; table name KEEP for now)
- `participation_options`, `participations`, `issue_comments`
- `issue_follows`, `issue_views`, `issue_user_events`
- `metric_snapshots`, `ingest_cursors`, `usage_events`

Child FK **column** names may still be `signal_id` (points at `issues.id`) — logical Issue id; physical column rename is optional follow-up.

---

## KEEP / MODIFY / DONE

| Object | Decision |
| --- | --- |
| `raw_items` | KEEP |
| `events` | KEEP / MODIFY as story spine |
| **`issues`** | DONE rename from `signals` |
| `signal_sources` | KEEP name; FK → `issues` |
| `participations*` | KEEP |
| Retention tables | KEEP |
| Watchlist / briefs / macro | KEEP (not primary Home) |

---

## Rename migration

`20260921_rename_signals_to_issues.py`:

```text
ALTER TABLE signals RENAME TO issues;
```

SQLite local: `session.init_db` also renames if old table present.

---

## Rollback

Restore from backup or reverse rename `issues` → `signals` only on empty/dev DBs. Production: forward-only.
