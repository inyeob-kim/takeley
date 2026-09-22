# 08 — Database Migration Plan

## Principles

- Additive migrations; no drop of `signals` in first cut
- SQLite + Postgres paths both considered (`DATABASE_URL`)
- Alembic preferred for new tables (`backend/alembic/`)

## Phase A — Additive tables (safe)

1. `participation_options`
2. `participations` (unique issue_id+user_id)
3. `comments` (+ optional `comment_likes`)
4. `issue_metrics` or columns on parent

## Phase B — Issue representation

**Option 1 (recommended):** treat `signals` as Issues

- Add nullable columns: `category`, `topic`, `trend_score`, `participation_type`, `participation_question`, `participation_suitable`
- Keep old finance columns for compatibility
- API maps Signal → IssueOut

**Option 2:** new `issues` table + `issue_id` on signal / 1:1 migration job

Prefer Option 1 until schema stabilizes.

## Phase C — Soft rename (later)

Views/aliases, then rename tables when clients fully cut over.

## Data backfill

- Existing published Signals → Issues without participation (read-only cards) OR batch LLM to add questions selectively
- Do not auto-generate forced binary for all historical rows

## Indexes

- `(status, published_at)`, `(trend_score)`, `(category)`
- participations `(issue_id)`, `(user_id, created_at)`
- comments `(issue_id, created_at)`

## What not to delete early

`raw_items`, `events`, `usage_events`, `market_briefs`, `watchlist_items`, `macro_events` — keep even if UI hides.
