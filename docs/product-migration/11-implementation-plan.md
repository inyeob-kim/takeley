# Implementation Plan — Issue + Participation Migration

> Based on `docs/product-migration/01–10`. **Preserve existing assets.** No big-bang rewrite.
> Status: **In progress / MVP scaffold shipped** (Phases 1–6 code landed 2026-09-20).

---

## Goal

Ship MVP loop:

**Issue Card → Participate → See others → (optional) Comment**

While keeping: X/News ingest, cluster→LLM funnel, quotas, cost tracking, device/push.

---

## Non-goals (MVP)

- Delete X / LLM / cost / brief / calendar / watchlist **code**
- Social graph, DM, money, prediction markets, gamification
- Flutter full UI (React prototype first)
- Forced binary debate on every item

---

## Approach decisions (locked for this plan)

| Decision | Choice | Why |
| --- | --- | --- |
| Issue storage | **Extend `signals` table** (Option 1) | Fastest; dual API; no data wipe |
| New APIs | **Additive `/api/v1/issues*`** | Signals stay for rollback |
| Finance UI | **Hide tabs**, don’t delete | Watchlist/calendar/brief DEFER |
| Participation | One vote/user; AI picks type or `suitable=false` | No Polymarket |
| Cap | Rename behavior to **daily Issue cap ~5–10** | Quality > quantity |

---

## Phases

### Phase 0 — Align (no code)

- [ ] Confirm this plan
- [ ] Confirm MVP nav: `Home | My Activity | Settings` (calendar/watchlist hidden)
- [ ] Confirm React-first (Flutter later)

**Exit:** Written approval to start Phase 1.

---

### Phase 1 — Database (additive)

**Files:** `backend/app/db/models/__init__.py`, new Alembic revision, SQLite patch path if used.

1. Add columns on `signals` (nullable):  
   `category`, `topic`, `trend_score`, `participation_type`, `participation_question`, `participation_suitable`
2. New tables:  
   `participation_options`, `participations` (unique `issue_id+user_id`), `comments`
3. Optional: `issue_metrics` or counter columns later

**Tests:** model create + unique vote constraint.

**Exit:** Migration applies cleanly on SQLite (and Postgres if configured). Existing Signal reads still work.

---

### Phase 2 — Issue API (adapter over Signals)

**Files:**  
`backend/app/schemas/__init__.py`, new `api/v1/issues.py`, `services/issue_service.py` (or extend signal_service), `router.py`

| Endpoint | Behavior |
| --- | --- |
| `GET /issues` | Published feed; sort `new` then `trending` (trend_score / importance) |
| `GET /issues/{id}` | Detail + options + counts + `my_option_id` |
| `POST /issues/{id}/participate` | Upsert vote |
| `GET /issues/{id}/comments` | List |
| `POST /issues/{id}/comments` | Create |
| `POST /issues/{id}/events` | impression/open (lightweight) |

Map existing Signal rows → IssueOut (participation empty until Phase 3).

**Keep:** `/signals`, `/settings`, `/push`, `/cost`, `/billing`.

**Exit:** curl/API tests; old Signal list still OK.

---

### Phase 3 — AI pipeline MODIFY (not replace)

**Files:** `pipeline/prompts.py`, `analyze.py`, `process_signals.py`, `config.py` (issue cap aliases)

1. New prompt version: Issue card + optional participation fields  
2. Rule: `participation_suitable=false` → no forced options  
3. Persist new fields + create `participation_options` on publish  
4. Cap: keep soft/hard ceiling semantics as **Issue** daily quality cap  
5. Heuristic fallback: publish read-only Issue if LLM fails

**Do not:** remove X ingest, cheap_filter, cluster, quality, usage recording.

**Exit:** Worker publishes Issues with/without options; cost events still logged.

---

### Phase 4 — React UI MVP

**Files:** `frontend/src/App.tsx`, Home, new IssueCard/Detail, api clients

1. Home → Issue Feed (뜨는 / 최신)  
2. Issue Card → Detail (summary, points, sources, vote, results, comments)  
3. Nav: hide Watchlist + Calendar (keep routes behind flag or Settings)  
4. Brief/TTS: remove from Home hero (code stays)  
5. My Activity: simple list of my votes (can be minimal screen)

**Exit:** Manual UX pass — read → vote → see count → comment.

---

### Phase 5 — Metrics + polish

1. Track impression / open / participation for **participation rate**  
2. Empty/error states; no participation UI when unsuitable  
3. Prompt calibration pass (no fake controversy)  
4. Update cursor product rules copy later (optional)

---

### Phase 6 — Cleanup (only after MVP works)

- Feature-flag brief/calendar/watchlist  
- Deprecate `/signals` when clients fully on `/issues`  
- **Still no mass delete** of providers/pipeline

---

## Suggested sprint slices

| Slice | Delivers | Depends |
| --- | --- | --- |
| S1 | Phase 1 DB | Phase 0 |
| S2 | Phase 2 read APIs + feed from existing Signals | S1 |
| S3 | Phase 2 participate + comments | S2 |
| S4 | Phase 3 prompt + option generation | S2 |
| S5 | Phase 4 Home + Card | S2 |
| S6 | Phase 4 Detail + vote UI | S3 |
| S7 | Phase 5 metrics | S6 |

---

## Risk checklist

| Risk | Plan mitigation |
| --- | --- |
| Break Signal clients | Dual API; adapter |
| Cost spike | Keep cheap_filter + hard Issue ceiling |
| Fake debates | `participation_suitable` + QA |
| Empty feed | Backfill: old Signals as read-only Issues |
| Over-deletion | DEFER = hide, not `rm` |

---

## Definition of done (MVP)

User opens app → understands Issue in seconds → taps opinion → sees aggregates → can comment — without finance dashboard.

---

## Next action

Reply with **“Phase 1 진행”** (or adjust nav/storage decisions first). Until then, no application code changes beyond this plan doc.
