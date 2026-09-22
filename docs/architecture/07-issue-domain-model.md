# 07 — Issue Domain Model (TAKELEY)

## Core separation

| Concept | Meaning | Persistence |
| --- | --- | --- |
| **RawItem** | Fetched internet atom | `raw_items` |
| **Candidate** | RawItem worth clustering | score / pool (implicit) |
| **Event / Story cluster** | Same-story group | `events` |
| **Issue** | User-facing card | **`issues`** (renamed from `issues`) |
| **Take** | User participation (vote) | `participations` |
| **Follow / View / Events** | Retention | `issue_follows`, `issue_views`, `issue_user_events` |

```text
RawItem ──< EventRawItem >── Event/Story
                                │
                                └── Issue (1 card, updatable)
                                      ├── sources / evidence
                                      ├── ParticipationOption
                                      ├── Participation (Take)
                                      ├── IssueComment
                                      ├── IssueFollow
                                      └── IssueView
```

---

## Issue fields (product)

On `issues` / domain card model:

- `title`, `summary`, `why_it_matters`, `key_points`, `column_body`, `image_url`
- `category`, `topic`, `trend_score`, `is_trending`, `source_reply_peak`
- `participation_*`
- `impression_count`, `open_count`
- `status` (`draft` / `published` / `rejected`)
- `lifecycle`, `trend_status`
- `content_updated_at` (retention clock — not ORM `updated_at`)

Finance leftovers (nullable KEEP): `related_symbols`, `market_reaction`, `content_type`, `evidence_level`.

---

## Lifecycle

```text
CANDIDATE (draft) → PUBLISHED → UPDATED → STALE / ARCHIVED
```

Admin publish is required before Home exposure.

---

## Participation (Take)

- One vote per `(issue_id column: signal_id, user_id)` until column rename
- Options rows; AI may set `participation_suitable=false` (read-only Issue)
- Comments flat
- Do **not** force debate; no prediction markets

---

## Storage decision (resolved)

| Decision | Status |
| --- | --- |
| Physical table **`issues`** | DONE (rename from `issues`) |
| ORM class **`Issue`** (`Signal` alias for compat) | DONE |
| Public API **`/api/v1/issues*`** | Primary |
| Legacy **`/api/v1/signals*`** | KEEP deferred / ops |
