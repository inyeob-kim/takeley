# 05 — Candidate Detection (revised)

## Role

> Is this RawItem worth spending an **LLM Understanding** call on?

Candidate Detection does **not** decide Issue meaning, sameness, or publishability.

---

## Deterministic only (cost / priority)

Allowed:

- spam / tipster / empty (`cheap_filter`)
- exact + fingerprint dup (`RawItemRepository`)
- age cutoff
- priority score for ordering into Top-N pool:

```text
recency, log(engagement), reply_count, provider_prior
```

**Forbidden as Issue hard gates:**

- min reply count
- min engagement score
- keyword / entity match
- “must be trending”

`pick_hottest` / `issue_heat` may **cap pool size** for X API/LLM budget only.

---

## Output

```text
Candidate {
  raw_item_id
  priority_score
  reasons[]          # priority reasons, not “is an Issue”
  metrics_snapshot?
  accepted_into_pool: bool
}
```

Persistence: payload / log first; optional table later.

---

## Next step (not this module)

Accepted candidates → **LLM Understanding** (see `18-llm-decision-model.md`).
