# 02 — Pipeline Problems

## Verdict

The stack is a **strong Common-Intelligence ingest + finance Signal factory**, with an Issue/Participation layer on table **`issues`** (ex-`signals`) + topic search + `issue_card_v3`.

It is **not yet** an Issue discovery system whose primary object is “one story people should care about and vote on.”

**Plan correction:** An intermediate plan treated entity+time clustering as the semantic judge. That is rejected. Final migration makes **LLM Understanding + LLM Match** the meaning layer; deterministic heat/cluster only control cost and shortlists (see `06`, `18`, `15`).
---

## Problem A — Popular tweet ≠ Issue

**Evidence**

- Topic path keeps individual hot posts (`pick_hottest`, keep ≤8).
- Clustering is near-duplicate **wording** (`cluster_items`, threshold 0.82), not same-story semantics.
- Distinct phrasings of one event → multiple clusters → multiple Signals/Issues.

**Product impact:** Feed shows near-duplicate cards; participation fragments across clones.

---

## Problem B — Absolute engagement bias

**Evidence:** `issue_heat.engagement_score`

```text
likes + 3*replies + 2*rts + 2.5*quotes
```

No recency decay, no velocity (Δmetrics / Δt), no first-seen vs peak comparison.  
`public_metrics` is a single snapshot at fetch — we never re-fetch metrics to compute velocity.

**Product impact:** Old viral posts outrank early emerging debates; “급상승” is mostly AI flag + reply floor, not measured acceleration.

---

## Problem C — `has:replies` collapses discovery & quality

**Evidence:** All `DEFAULT_INDUSTRY_X_QUERIES` include `has:replies`.

Early posts with 0 replies never enter the candidate set. Discovery and engagement gates are fused at the API query layer.

**Product impact:** Blind spot for just-breaking stories; over-indexes on already-discussed threads.

---

## Problem D — Fixed industry queries

**Evidence:** `industries.py` hardcoded OR-lists (AI/Tech/Finance/Economy/Politics).

Good for MVP coverage; bad for emerging slang, non-English spikes, or topics outside the keyword bag.

**Decision:** Keep for Phase 1–4; **Dynamic Query = Phase 2+ / deferred** (see 14).

---

## Problem E — Dual identity on `issues`

Finance fields (`related_symbols`, `market_reaction`, `content_type`, publish quota by ticker) still drive process ordering and gates. Topic Issues piggyback via importance bumps / participation requirement.

**Product impact:** Quota and “underserved symbols” optimize for ticker fairness, not Issue diversity or participation quality.

---

## Problem F — Weak lifecycle

Existing update path: same `event_id` published Signal gets fields overwritten (`process_signals` existing branch). No explicit:

`DISCOVERED → CANDIDATE → PUBLISHED → ACTIVE → STALE → ARCHIVED`

No trend_score time series; `is_trending` is a bool set at analyze time.

---

## Problem G — Evidence trust is partial

`classification.py` / `quality.py` distinguish community vs news/official for **confirmed_fact**. Topic clusters are often X-only → correctly low evidence, but UI still presents as Issue Card without a first-class Source Trust layer on the card spine.

---

## Problem H — Metric mismatch

Ops logs: fetched/inserted/created/rejected/quota.  
Product needs: candidate_count, cluster_count, duplicate_prevented, participation_rate.

Impressions/opens exist (`impression_count`/`open_count`) but are not wired into pipeline scoring.

---

## Problem I — Issue feed polluted by finance Signals

`IssueService.list_issues` selects all published `issues` rows. Topic Issues and ticker/finance cards share one table and one list. Home can show non-Issue cards unless the client filters.

---

## Problem J — Schema drift (SQLite vs Alembic)

`is_trending` / `source_reply_peak` are ensured for SQLite via `db/session.py` `_ensure_sqlite_columns`, but **`20260920_issue_participation.py` does not add them**. Postgres (or clean Alembic-only) deploys can miss columns.

---

## Problem K — Operational gaps in providers

- X: no pagination, no 429 backoff  
- News: `since_id` cursor written but unused  
- Reddit stub always returns `[]` yet still invoked each ingest  
- Raw rows dropped pre-cluster still marked `processed=1` → silent loss for reprocessing

---

## Mapping to desired pipeline gaps

| Desired stage | Today | Gap |
| --- | --- | --- |
| Candidate Detection | heat + cheap_filter + keep | No velocity/diversity score object |
| Emerging Topic | none | Keyword bag only |
| Semantic Clustering | text near-dup | Need embeddings + time + entities |
| Issue Candidate | implicit cluster | No first-class candidate entity |
| Evidence aggregation | SignalSource attach | No trust ranking / claim grounding UI contract |
| LLM structuring | analyze_cluster | Still mixed with finance Signal schema |
| Lifecycle / dedupe Issues | event_id update | No cross-key merge / archive |
| Participation | LLM fields + tables | Forced suitability gate on topic path only |
