# 01 — Current Architecture

> Audit only. No code changes. Snapshot of Market Radar as of 2026-09-20.

## Product today

Korean 4060 서학개미-oriented **US market intelligence** app:

```text
Sources → Worker ingest → Pipeline → DB → API personalization → React app
```

- **Core unit:** Event / Signal (not raw posts)
- **LLM:** worker pipeline (+ explicit Ask AI exception on signal detail)
- **Not:** X-repost bot, Bloomberg terminal, per-request live search

## Backend layers

| Layer | Path | Role |
| --- | --- | --- |
| API | `backend/app/api/v1/` | HTTP only |
| Services | `backend/app/services/` | Read/personalize/brief/push/cost |
| Pipeline | `backend/app/pipeline/` | normalize → cheap filter → cluster → analyze → quality → quota |
| Providers | `backend/app/providers/` | X / News / Reddit / Official / Calendar / DART / Symbol |
| Domain / Schemas | `backend/app/domain/`, `schemas/` | Pydantic models + API DTOs |
| DB | `backend/app/db/models/` | SQLAlchemy tables |
| Worker | `backend/worker/` | ingest, process_signals, brief/TTS, calendar, push |

## Worker loops (`backend/worker/main.py`)

1. **Heavy cycle** (ingest interval): `sync_calendar` → `run_ingest` → `run_process_signals`
2. **Brief poll**: `run_generate_brief` + TTS queue
3. **Push**: `run_pending_push`

## Ingest sources (`backend/worker/jobs/ingest.py`)

- X account timelines (`X_TRACK_ACCOUNTS`)
- X symbol search (monitor set ∪ watchlist, budget + rotation)
- Google News RSS (per-symbol, article body fetch)
- Optional KR path (DART + KR news; default off)
- Reddit / Official stubs where enabled

Gate: `is_keep_for_intelligence` = symbol match **or** macro theme keywords.

## Process pipeline (`backend/worker/jobs/process_signals.py`)

```text
raw_items → cheap_filter → cluster → analyze (LLM/heuristic)
→ quality gate → Event upsert → publish quota → Signal + SignalSource
→ optional push enqueue
```

## API surface (`backend/app/api/v1/router.py`)

| Router | Prefix / focus |
| --- | --- |
| `signals.py` | list / detail / explain (+ SSE stream) |
| `watchlist.py` | CRUD watchlist |
| `brief.py` | today’s brief + audio |
| `assets.py` | symbol search / catalog |
| `calendar.py` | macro calendar from DB |
| `settings.py` | alarm / TTS voice prefs |
| `billing.py` | device entitlement / IAP product ids |
| `push.py` | device token + templates |
| `cost.py` | usage / cost estimates |

## Persistence (key tables)

- `raw_items`, `events`, `event_raw_items`
- `signals`, `signal_sources`
- `assets`, `watchlist_items`
- `market_briefs`
- `macro_events`
- `users`, `user_preferences`, `device_tokens`
- `usage_events`, `push_*`, `ingest_cursors`
- `subscription_payments`

Auth today: **device-linked user** (not full OAuth social graph). Alembic exists; SQLite also uses runtime patches for some columns.

## Frontend (actual UI)

**Product UI lives in React** under `frontend/` (Vite), not Flutter screens.

| Tab / screen | Path |
| --- | --- |
| Home (brief + signals + calendar peek) | `frontend/src/screens/HomeScreen.tsx` |
| Watchlist | `WatchlistScreen.tsx`, `WatchlistSignalsScreen.tsx` |
| Calendar | `CalendarScreen.tsx` |
| Settings | `SettingsScreen.tsx` |
| Signal detail + Ask AI | `SignalDetailScreen.tsx`, `SelectableAskBody.tsx`, `ExplainBottomSheet.tsx` |
| Audio brief player | `AudioPlayerScreen.tsx` |
| Nav | `frontend/src/App.tsx` — tabs: home / watchlist / calendar / settings |

## Mobile (`mobile/`)

Flutter is an **FCM scaffold only** (`mobile/lib/main.dart`): device session + push registration. No Issue/Signal feed UI yet. Product target remains Flutter later; near-term prototype is React.

## Cost / observability

- `backend/app/core/usage.py` — event counters
- `backend/app/services/cost_service.py` + `cost_pricing.py` + `api/v1/cost.py`
- Caps: `daily_signal_*`, `x_search_query_budget`, `explain_daily_cap`, push daily cap

## Strengths to preserve

1. Shared intelligence (one ingest/analyze for many users)
2. Multi-source providers behind a common RawItem shape
3. Cost funnel + quotas already wired
4. Evidence / content_type discipline in prompts & quality
5. Device user + push + settings foundation

## Gaps vs new Issue product

1. No Participation / Comment models or APIs
2. Signal schema is finance-first (`related_symbols`, market reaction, tipster filters)
3. Home UX = brief + watchlist finance, not Issue cards
4. Ranking = recency + watchlist boost, not trend/participation
5. Flutter product UI not built yet
