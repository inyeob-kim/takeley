# 18 — LLM Decision Model

## Boundary

| Decision | Deterministic | LLM |
| --- | --- | --- |
| Exact / fingerprint duplicate | O | |
| Spam / empty / tipster | O | Understanding may confirm |
| Age cutoff | O | |
| Candidate pool priority / size | O | |
| Engagement/replies as Issue **create** hard gate | **Forbidden** | |
| Topic / event / claim / novelty / relevance | | Understanding |
| Same vs different Issue (paraphrase vs new event) | pregroup/shortlist only | **Match** |
| NEW / UPDATE / REJECT | shortlist candidates | **Match** |
| Card copy + participation suitability | | Structuring |
| Trending | heat evidence | + Structuring suggestion |
| Schema / grounding / daily Issue cap | O | |
| Keyword / entity / time as final same-Issue | **Forbidden** | |

## Understanding (illustrative; tune to code)

Not a blind copy — align with existing JSON + Pydantic validation:

```json
{
  "is_issue_candidate": true,
  "relevance": 0.0,
  "topic": "",
  "event": "",
  "claim": "",
  "entities": [],
  "novelty": "new_development|commentary|duplicate_suspected",
  "participation_suitable_hint": false
}
```

## Match (illustrative)

```json
{
  "decision": "NEW_ISSUE|UPDATE_EXISTING|REJECT",
  "existing_issue_id": null,
  "confidence": 0.0,
  "reason": ""
}
```

## Cost controls

- `ISSUE_LLM_UNDERSTAND_BUDGET_PER_CYCLE`
- Match only for `is_issue_candidate=true`
- Shortlist size capped
- No raw-firehose LLM
- No embedding / second judge in MVP
