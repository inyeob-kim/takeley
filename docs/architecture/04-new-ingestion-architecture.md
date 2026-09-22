# 04 — New Ingestion Architecture

## Goal

Reuse providers + cursors + cost tracking. Change **what success means**:  
not “hot tweets stored,” but “raw material that can become Issue candidates.”

---

## Target topology

```text
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ X Accounts  │  │ X Discovery │  │ RSS / News  │  │ Web / DART  │
│ (seed)      │  │ Search      │  │ (+ body)    │  │ (defer KR)  │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       └────────────────┴────────────────┴────────────────┘
                                ↓
                         Raw Ingestion
                    (upsert_many + cursors)
                                ↓
                      Normalize / Dedup
                                ↓
                      Candidate Detection   ← NEW emphasis
                                ↓
                    (rest: clustering → Issue — docs 05–08)
```

Worker still owns all external I/O (`architecture.mdc`).

---

## Source roles (reframed)

| Source | Role in Issue product |
| --- | --- |
| X Discovery Search | Primary **candidate discovery** by industry |
| X Accounts | High-signal seeds / corroboration |
| RSS + article body | Trusted narrative + facts |
| X Ticker Search | Optional corroboration / DEFER from Issue MVP |
| DART / KR | DEFER |
| Reddit | DEFER |

---

## Discovery vs Engagement (split)

### Discovery query (proposed)

- Industry keyword OR-lists **without** mandatory `has:replies`.
- Prefer broader recall; cap with `X_TOPIC_QUERY_BUDGET` / keep-per-query.

### Engagement / heat (post-fetch)

- Used only to **rank and cap** Candidate Pool size (API/LLM budget).
- **Must not** hard-reject Issue creation solely for low replies/engagement.

`has:replies` moves from query mandatory → optional quality preference.

---

## Industry rotation (KEEP pattern, change goal)

Keep:

- `ISSUE_INDUSTRIES`
- `X_TOPIC_QUERY_BUDGET`
- `topic:rotate_offset`
- `topic:{industry}:since_id`
- `topic:last_fetch_at`

Change goal:

```text
BEFORE: Industry → Top 8 hot tweets
AFTER:  Industry → Candidate pool for emerging stories
```

`ISSUE_TOPIC_KEEP_PER_QUERY` becomes “max candidates retained per industry per cycle,” not “final Issues.”

---

## Raw item contract (KEEP + extend payload)

Keep columns on `raw_items`. Extend `raw_payload` conventions:

```json
{
  "issue_industry": "ai",
  "issue_category": "AI",
  "search_query": "...",
  "public_metrics": { "...": 0 },
  "ingest_mode": "discovery|deep_fetch|account|rss",
  "fetched_metrics_at": "ISO-8601"
}
```

Do not invent a second raw store.

---

## Scheduling sketch (final numbers after cost — 09 / 10)

| Lane | Intent | Starting band |
| --- | --- | --- |
| Discovery | Industry search | 5–15 min (quota-bound) |
| Accounts | Seed | 30–60 min |
| RSS | Stable evidence | 30–60 min |
| Hot follow-up | Re-fetch metrics / related search for active Issues | 5–10 min |
| Heavy process | Candidate→Issue | Align with discovery or slightly slower |

`TEST_FAST_INGEST` remains local override.

---

## What does **not** change in Phase 1–2

- Provider adapters stay behind `SourceProvider`
- No Dynamic Query Generation
- No scraping / unofficial X endpoints
- API still DB-only
