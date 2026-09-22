# 09 — Fetch Scheduling

## Current (code)

| Mechanism | Location | Behavior |
| --- | --- | --- |
| Heavy wake | `worker/main.py` + `JobScheduler` | `ingest_interval_seconds` |
| Source due | `ingest._ingest_due` | per cursor timestamp |
| Test clamp | `TEST_FAST_INGEST` | all ingest intervals → 60s |
| Calendar | `sync_calendar` | `calendar_sync_interval_seconds` (86400) |
| Brief poll | main thread | 60s (deferred product) |

Defaults: heavy 1800; X accounts/RSS 3600; X search/topic 1800.

---

## Problems

1. Wake interval and source intervals are independent — easy to wake and do nothing (`not_due`).
2. One flat topic interval for all industries.
3. No hot-path follow-up for active Issues.
4. Discovery cost not isolated from deep evidence fetch.

---

## Proposed lanes

| Lane | Sources | Starting band* | Cursor idea |
| --- | --- | --- | --- |
| Discovery | X industry search (no has:replies) | 5–15 min | `topic:discovery:last_fetch_at` |
| Seed | X accounts | 30–60 min | existing accounts cursor |
| Evidence | RSS + body | 30–60 min | existing rss cursor |
| Deep / follow-up | Re-search / re-metric hot Issues | 5–10 min | `issue:{id}:followup_at` |
| Process | candidate→Issue | every discovery or ≤15 min | can share heavy cycle |

\*Bands are **placeholders**. Lock after X monthly cap + cost sim (10).

---

## Config shape (additive)

Keep existing env vars. Add later:

```text
DISCOVERY_INTERVAL_SECONDS=
FOLLOWUP_INTERVAL_SECONDS=
ISSUE_PROCESS_INTERVAL_SECONDS=
```

Or map lanes onto existing keys with clearer names in docs/code comments first.

`TEST_FAST_INGEST` continues to clamp **all ingest lanes** for local loops.

---

## Topic rotation

KEEP `X_TOPIC_QUERY_BUDGET` + `topic:rotate_offset`.

Under tight quota: fewer industries per discovery tick, faster wake.  
Under loose quota: budget=all industries each tick.

---

## Rate limit / retry

Today: mostly log exception and continue (per industry / symbol).  
MODIFY: exponential backoff cursor “cooldown until” on 429; record `usage_events` with error tags.

No silent infinite retry storms.
