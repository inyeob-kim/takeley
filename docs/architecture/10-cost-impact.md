# 10 — Cost Impact

## Existing cost infrastructure (KEEP)

| Piece | Path |
| --- | --- |
| Usage counters | `app/core/usage.py` (`X_API_REQUESTS`, `X_SEARCH_REQUESTS`, LLM helpers) |
| Pricing map | `app/core/cost_pricing.py` |
| Projection API | `app/services/cost_service.py`, `api/v1/cost.py` |
| DB | `usage_events` |

Continue logging model, cluster size, success/fail — never secrets.

---

## Cost drivers

| Driver | Today | Redesign pressure |
| --- | --- | --- |
| X search requests | ticker budget + topic industries | Discovery more frequent → **up** unless budget tightened |
| X tweet volume | metrics on each hit | Discovery without has:replies → more posts → heat filter must drop hard |
| RSS + HTML fetch | per symbol heavy | KEEP; don’t increase for Issue MVP |
| LLM analyze | per cluster | Semantic merge should **reduce** clusters → LLM **down** or flat |
| Embeddings | **none** | NEW cost line — batch, fingerprint cache |
| Brief/TTS | separate | DEFER — ignore in Issue MVP cost |

---

## Design principles

```text
Fetch wider (discovery)
 → Filter cheaper (candidate score)
 → Cluster better (fewer LLM calls)
 → LLM only on Issue Candidates
```

Never: embed all raw firehose, or LLM each tweet.

---

## Expected direction (qualitative)

| Item | Direction |
| --- | --- |
| X API | ↑ if discovery wider/faster — control with budgets |
| LLM | **3 stages** (Understanding, Match, Structuring) but on **Top-N candidates**, not all raw → aim net flat-to-moderate ↑ vs today’s 1×/text-cluster |
| Embeddings | **0 in MVP** |
| 2nd quality LLM | **0 in MVP** |

Caps: `ISSUE_LLM_UNDERSTAND_BUDGET_PER_CYCLE`, match shortlist size, topic keep/budget.

Lock numbers after measuring Understanding+Match on a sample day — do not raise intervals blindly.

---

## Guardrails

- Keep `X_TOPIC_QUERY_BUDGET`, `X_SEARCH_QUERY_BUDGET`
- Daily Issue hard ceiling
- Cap embeds per heavy cycle
- Cap re-analyze per Issue per day
- `TEST_FAST_INGEST=false` in any shared/prod env
