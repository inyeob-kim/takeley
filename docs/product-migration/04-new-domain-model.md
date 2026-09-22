# 04 — New Domain Model

## Principles

- Prefer **evolving `signals` → issues** (or additive `issues` table with migration from signals) over greenfield wipe.
- Keep `raw_items` / `events` / sources as upstream truth.
- Finance assets are **optional links**, not the spine.
- Participation types are enum + options rows; don’t invent markets.

## Core entities

### Issue (from Signal)

| Field | Notes |
| --- | --- |
| id | reuse signal id or new UUID with mapping |
| title | short card title |
| summary | short body |
| why_it_matters | optional; rename UX “왜 중요한가” |
| key_points | JSON list |
| source_references / source_count | via `signal_sources` |
| category | e.g. Technology, Markets, Politics |
| topic | free or curated slug |
| trend_score | float; start = f(importance, recency, source_diversity) |
| participation_type | `binary` \| `choice` \| `sentiment` \| `opinion` \| `prediction` |
| participation_question | string |
| status | draft / published / rejected |
| created_at / updated_at / published_at | existing timestamps |
| related_assets | optional JSON (was `related_symbols`) |

**Do not force** participation on every cluster. If AI marks `participation_suitable=false`, publish as read-only Issue or skip publish.

### ParticipationOption

```text
id, issue_id, label, display_order, color_hint?
```

### Participation

```text
id, issue_id, user_id, option_id, created_at
UNIQUE(issue_id, user_id)  -- one vote per user in MVP
```

### Comment

```text
id, issue_id, user_id, content, like_count, created_at
```

MVP: flat comments, like toggle optional table `comment_likes`.

### IssueMetrics (or computed)

```text
impression_count, open_count, participation_count, comment_count
```

Can start as counters on Issue or separate events table for analytics.

### Upstream (KEEP)

- `RawItem`, `Event`, `EventRawItem`, `SignalSource` (rename association later)
- `User` (device-linked), `UserPreference`, `UsageEvent`

### Optional / later

- `Topic`, `TopicFollow` (evolve watchlist)
- `IssueCommentSummary` (AI rollup when comment_count ≥ N)

## Mapping from current Signal

| Signal field | Issue field |
| --- | --- |
| title / summary / why_it_matters / key_points | same |
| importance | seeds trend_score |
| related_symbols | related_assets (optional) |
| related_sectors | category/topic hints |
| content_type / evidence_level / evidence_mix | keep for quality; less prominent in UI |
| market_reaction / emphasis | finance-only optional |
| sources | source_references |

## Participation type policy

AI chooses type; rules:

- Factual color/product launch with no debate → **no forced binary**; skip or soft sentiment
- Clear contested outlook → binary / prediction (non-monetary)
- Multi-outcome → choice (≤3–4 options)
