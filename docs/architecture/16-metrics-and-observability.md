# 16 — Metrics and Observability

## Pipeline counters (usage_events or dedicated metrics)

```text
raw_items_fetched
candidate_accepted / candidate_rejected
llm_candidate_analysis          # Understanding calls
llm_issue_match
clusters_pregrouped             # lexical only
issue_created / issue_updated
duplicate_issue_prevented       # Match → UPDATE or REJECT dup
issue_quality_rejected
issue_published
```

## Product counters (existing + derived)

```text
issue_impressions / issue_opens   # issues.impression_count / open_count
participations / comments
participation_rate = participations / unique openers
```

## Funnel

```text
Raw → Candidate → LLM Understanding → Match → Issue → Open → Participation
```

Wire stage tags into existing `app/core/usage.py` / cost rollup; do not invent USD without `cost_pricing`.
