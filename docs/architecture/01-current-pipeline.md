# 01 — Current Pipeline (code audit)

> Status: analysis only — no code changes.  
> Related earlier product docs: `docs/product-migration/*` (UI/API rename scaffold already shipped).  
> This series focuses on **ingestion → Issue discovery** redesign.

---

## End-to-end flow (as implemented)

```text
worker/main.py
  heavy_cycle (JobScheduler @ ingest_interval_seconds)
    → run_sync_calendar
    → run_ingest          # providers → raw_items
    → run_process_signals # raw → events → issues (+ Issue fields)
    → run_pending_push
  brief_cycle (separate thread @ brief_poll_interval_seconds)
    → generate_brief / TTS / push
```

**Invariant today:** API never calls X/News/LLM. Worker builds shared rows; `/api/v1/issues*` reads `issues` table (ORM: `Issue`, alias `Signal`).

---

## Ingestion (`backend/worker/jobs/ingest.py`)

Entry: `run_ingest(db)`.

| Order | Function | Provider | What it fetches |
| --- | --- | --- | --- |
| 1 | `_ingest_x_accounts` | `XProvider` | Configured account timelines |
| 2 | `_ingest_x_search` | `XProvider.fetch_search` | Per-ticker recent search (US universe) |
| 3 | `_ingest_x_topics` | `XProvider.fetch_search` | Industry keyword queries (Issue path) |
| 4 | `_ingest_news` | `NewsProvider` | Google News RSS + HTML body |
| 5 | `_ingest_dart` | `OfficialProvider` / DART | KR disclosures (if KR symbols) |
| 6 | `_ingest_kr_news` | `KoreanNewsProvider` | KR Google News (if enabled) |
| 7 | Reddit stub | `RedditProvider` | limit=5 demo-ish |

Due gating: `_ingest_due(cursor_repo, provider, cursor_key, interval_seconds)` using `ingest_cursors`.  
Mark: `_mark_ingest_fetch` writes ISO timestamp.

### X Accounts

- **API:** Tweepy `Client.get_users_tweets` (via `XProvider.fetch` / `fetch_account`)
- **Config:** `X_TRACK_ACCOUNTS`, `X_ACCOUNTS_INTERVAL_SECONDS` (default 3600)
- **Cursor:** `x` / `accounts:last_fetch_at`; per-account `since_id` keys
- **Filter:** `is_keep_for_intelligence` / symbol relevance against universe
- **Store:** `RawItemRepository.upsert_many`

### X Ticker Search

- **API:** `search_recent_tweets` (`XProvider.fetch_search`)
- **Query:** built by `search_query_for` / universe helpers (ticker + name)
- **Config:** `X_SEARCH_INTERVAL_SECONDS` (1800), `X_SEARCH_QUERY_BUDGET` (8)
- **Cursor:** `x` / `search:last_fetch_at`; rotate among symbols
- **max_results:** clamped 10–100 in provider; ingest uses ~10–15 style limits

### X Topic Search (Issue discovery path)

- **Files:** `ingest._ingest_x_topics`, `pipeline/industries.py`, `pipeline/issue_heat.py`
- **API:** same `search_recent_tweets`
- **Queries:** `DEFAULT_INDUSTRY_X_QUERIES` — e.g. AI:

```text
(AI OR ChatGPT OR OpenAI OR LLM OR "artificial intelligence")
lang:en -is:retweet has:replies
```

- **Config:** `ISSUE_INDUSTRIES`, `ISSUE_X_TOPIC_ENABLED`, `X_TOPIC_SEARCH_INTERVAL_SECONDS`, `X_TOPIC_QUERY_BUDGET`, `ISSUE_TOPIC_KEEP_PER_QUERY`, `ISSUE_MIN_*`
- **Cursors:** `topic:last_fetch_at`, `topic:rotate_offset`, `topic:{industry}:since_id`
- **Post-fetch:** `pick_hottest` → only hot posts upserted
- **Payload tags:** `issue_industry`, `issue_category`, `search_query`, `public_metrics`

### News / Google RSS

- **Files:** `providers/news_provider.py`, `providers/article_fetch.py`
- **API:** HTTP GET Google News RSS; then publisher HTML extract (trafilatura)
- **Interval:** `RSS_INTERVAL_SECONDS` (3600)
- **Cursor:** `news` / `rss:last_fetch_at`; also writes `rss:{symbol}:since_id` but **`NewsProvider.fetch` does not apply `since_id`** (gap)
- **Over-fetch:** `NEWS_RSS_PARSE_MULTIPLIER` / `NEWS_BODY_SCAN_MULTIPLIER`; body min/max chars
- **Drops:** no_body / too_short when `NEWS_FETCH_BODY=true` (headline-only never stored)

### X provider limits (all search/timeline paths)

- **API:** Tweepy `Client` + Bearer (`TWITTER_BEARER_TOKEN`); no bearer → demo items on some paths
- **Pagination:** none (`next_token` unused)
- **Retries / 429 cooldown:** none — log + continue / return `[]`
- **Search sort:** `sort_order="relevancy"`; `max_results` clamped 10–100

### DART / KR News

- Gated by KR universe + `DART_API_KEY` / `KR_NEWS_ENABLED`
- Intervals: `DART_INTERVAL_SECONDS`, `KR_NEWS_INTERVAL_SECONDS`

### Dedup at ingest

`RawItemRepository.upsert_many`:

1. Unique `(provider, external_id)`
2. Skip if `content_fingerprint` already exists (cross-source near-dup)

---

## Processing (`backend/worker/jobs/process_signals.py`)

```text
raw_repo.unprocessed(limit=100)
  → normalize + fingerprint
  → topic_heat_decision again (topic-tagged items)
  → is_keep_for_intelligence (non-topic) / cheap_filter
  → cluster_items (text near-dup, similarity 0.82)
  → analyze_cluster (LLM issue_card_v3 or heuristic)
  → is_trending ∧ reply_peak gate
  → topic_needs_participation gate
  → passes_quality_gate
  → Event upsert (cluster_key)
  → publish_quota / fair sort
  → Issue row + SignalSource + participation_options
  → mark_processed
```

**Physical store:** table `issues` (ORM `Issue` / alias `Signal`). UI uses `/api/v1/issues*`.

---

## Clustering today

`pipeline/cluster.py` + `dedupe.is_near_duplicate` — **token/text similarity only**. No embeddings, no time window, no entity overlap beyond co-clustering text.

---

## LLM today

| Stage | Module | When |
| --- | --- | --- |
| Analyze | `pipeline/analyze.py` + `prompts.py` (`issue_card_v3`) | Per cluster that reaches analyze |
| Brief select/synth | `select_signals`, `brief_synthesize` | Brief cycle (product-deferred UI) |
| TTS | `pipeline/tts.py` | Brief audio |

Cost funnel intent: filter → cluster → LLM. Topic heat runs **before** LLM (good). Absolute engagement still dominates discovery (problem — see 02).

---

## Scheduling

| Knob | Env | Default | Role |
| --- | --- | --- | --- |
| Heavy wake | `INGEST_INTERVAL_SECONDS` | 1800 | How often ingest+process run |
| Per-source | `X_*_INTERVAL_*`, `RSS_*` | 1800–3600 | Due inside wake |
| Test clamp | `TEST_FAST_INGEST` | false | Forces wake+source intervals → 60s |

Implemented in `Settings._apply_test_fast_ingest` (`config.py`).

---

## API surface (Issue product)

`backend/app/api/v1/issues.py` → `issue_service`:

- `GET /issues`, `GET /issues/{id}`
- `POST .../participate`, comments, impression/open events
- `GET /issues/activity/me`

Still dual with `/signals` for finance/rollback.

**Feed caveat:** `list_issues` returns **all** `status=published` `issues` rows. Finance-only cards (no category / not topic-origin) can appear on Home unless filtered — treat as MODIFY (see 02, 12).

**Process caveat:** `mark_processed` marks **every** loaded unprocessed raw row in the batch, including items dropped by heat/cheap_filter before clustering.

---

## DB tables involved

| Table | Role |
| --- | --- |
| `raw_items` | Source material |
| `events` + `event_raw_items` | Cluster identity |
| `issues` | **Issue store** (ex-`signals`) |
| `signal_sources` | Evidence links (FK → `issues.id`) |
| `participation_*`, `issue_comments` | Participation |
| `ingest_cursors` | Fetch due + since_id |
| `usage_events` | Cost proxies |
