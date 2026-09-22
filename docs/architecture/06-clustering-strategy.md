# 06 — Clustering / Grouping Strategy (revised)

## Principle change

**Final “same Issue?” judgment is LLM Issue Match — not keyword, entity, time, or embedding.**

| Layer | Purpose | Decides Issue identity? |
| --- | --- | --- |
| L0 lexical near-dup (`cluster.py`) | Collapse copy-paste / mirrors; shrink LLM batches | **No** |
| Optional shortlist by category / time window | Limit which existing Issues to show the Match LLM | **No** |
| Entity overlap | Optional hint in LLM prompt | **No** |
| Embedding similarity | **Phase B only** | **No** (even then: assist, not sole judge) |
| **LLM Issue Match** | NEW / UPDATE / REJECT | **Yes** |

---

## Deprecated plan item

Previous plan “Sprint 3 = entity + time L1 as semantic clustering” is **superseded**.  
Entity+time must not merge Case B (same NVIDIA, different events) or miss Case A (paraphrases).

---

## Flow

```text
LLM Understanding outputs
  → optional L0 pregroup (cost)
  → shortlist recent Issues (category/time)
  → LLM Match(new, shortlist) → NEW | UPDATE | REJECT
```

---

## Golden tests

See `13-testing-strategy.md` Cases A–E. Required before Match ships.
