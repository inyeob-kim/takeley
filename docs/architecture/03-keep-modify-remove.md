# 03 — KEEP / MODIFY / REMOVE

Legend: **KEEP** reuse as-is · **MODIFY** change behavior/API · **REMOVE** delete or stop calling · **DEFER** leave code, hide from product path.

---

## Ingestion / providers

| Component | Path | Decision | Notes |
| --- | --- | --- | --- |
| `SourceProvider` base | `providers/base.py` | KEEP | Extensibility contract |
| `XProvider` + bearer client | `providers/x_provider.py` | KEEP | search + timelines |
| X accounts ingest | `ingest._ingest_x_accounts` | MODIFY | Quality seed, not primary Issue invent |
| X ticker search | `ingest._ingest_x_search` | REMOVE from Issue default loop / DEFER | High cost ticker fan-out; optional later as Issue corroboration only |
| X topic search | `ingest._ingest_x_topics` | MODIFY | Discovery-first (drop/split `has:replies`) |
| `industries.py` queries | `pipeline/industries.py` | MODIFY | Keep keys; revise operators |
| `issue_heat.py` | `pipeline/issue_heat.py` | MODIFY | Add recency/velocity; split discovery vs quality |
| News RSS + body fetch | `news_provider`, `article_fetch` | KEEP | Cross-source evidence |
| DART / KR news | dart / korean_news | DEFER | KR MVP later; keep code |
| Reddit stub | `reddit_provider` | DEFER / REMOVE later | Not product-critical |
| Cursor due pattern | `_ingest_due`, `IngestCursor` | KEEP | Extend keys for discovery vs deep-fetch |
| `TEST_FAST_INGEST` | `config.py` | KEEP | Local retest only |

---

## Processing pipeline

| Component | Path | Decision | Notes |
| --- | --- | --- | --- |
| `normalize` / fingerprint | `normalize.py` | KEEP | |
| `cheap_filter` | `cheap_filter.py` | KEEP / MODIFY | Retune for social spam vs ticker noise |
| `is_keep_for_intelligence` | `normalize.py` | MODIFY | Topic path already bypasses; make explicit Candidate gate |
| `cluster_items` | `cluster.py` | MODIFY → NEW semantic layer | Keep as cheap pre-cluster |
| `analyze_cluster` + prompts | `analyze.py`, `prompts.py` | MODIFY | Issue-only schema path; finance optional |
| `quality` grounding | `quality.py` | KEEP | Evidence integrity |
| `classification` | `classification.py` | KEEP / MODIFY | Map to source trust |
| `publish_quota` symbol fairness | `publish_quota.py` | MODIFY | Daily Issue cap by category/topic diversity |
| `process_signals.py` | worker job | MODIFY → rename conceptually | Orchestrate new stages |
| Brief / TTS / select | brief_* , tts, select_signals | DEFER | Out of primary chrome |

---

## Data / API

| Component | Decision | Notes |
| --- | --- | --- |
| `raw_items` | KEEP | True raw material |
| `events` / `event_raw_items` | MODIFY | Evolve toward Issue Candidate / Story |
| `issues` (ex-`signals`) | DONE | Physical rename shipped; child cols may still be `signal_id` |
| `signal_sources` | KEEP / MODIFY | Add trust_tier |
| participation tables | KEEP | Already correct product shape |
| `/api/v1/issues*` | KEEP / MODIFY | Stable contract; **filter feed** to Issue-product rows; enrich fields |
| Alembic Issue cols | MODIFY | Add `is_trending`, `source_reply_peak` to revision for non-SQLite |
| News `since_id` | MODIFY or drop | Either apply in `NewsProvider` or stop writing unused cursors |
| `mark_processed` batch | MODIFY | Only mark clustered/handled ids; or status enum on raw |
| `/api/v1/signals*` | DEFER | Rollback / ops |
| Watchlist / calendar / brief APIs | DEFER | Not delete |

---

## Cost / worker infra

| Component | Decision |
| --- | --- |
| `usage.py`, `cost_pricing`, `cost_service`, `/cost` | KEEP |
| `JobScheduler`, heavy/brief split | KEEP / MODIFY scheduling tiers |
| Push enqueue | DEFER for Issue alerts later |

---

## Explicit REMOVE (behavior, not necessarily delete files yet)

1. Heat / reply / `has:replies` as **Issue create** hard gates
2. Lexical / entity / time as **final** same-Issue judge
3. `topic_needs_participation` hard reject
4. Symbol underserved as primary Issue publish optimizer
5. Entity+time L1 “semantic cluster” plan item (superseded by LLM Match)
6. Finance-only rows in default `/issues` Home feed

---

## NEW components (design-level)

- Candidate Detection (`candidate.py`) — **priority only**
- LLM Understanding stage (+ prompt version)
- LLM Issue Match stage (+ prompt version)
- Evidence aggregation + `trust_tier`
- Issue Quality Gate (deterministic)
- Funnel metrics (16), lifecycle / trend_status (17)
- **Not NEW for MVP:** embedding clusterer, velocity scorer, dynamic queries
