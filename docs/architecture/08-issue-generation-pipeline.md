# 08 — Issue Generation Pipeline (revised)

## Target funnel

```text
Raw Items
 → Cheap deterministic filter          (spam/dup/age)
 → Candidate Pool                      (priority / budget — not meaning)
 → LLM Understanding                   (topic, event, claim, novelty, relevance)
 → Optional lexical pregroup           (cost only)
 → LLM Issue Match                     (NEW | UPDATE | REJECT)
 → Evidence Aggregation                (multi-source; signal_sources)
 → LLM Issue Structuring               (card JSON; evolve issue_card_v*)
 → Deterministic Quality Gate          (schema, grounding, evidence present)
 → Publish (issues)                   (soft daily Issue cap + diversity)
 → Issue Card → optional Participation
```

---

## LLM stages (worker only)

| Stage | Prompt home | Output role |
| --- | --- | --- |
| Understanding | NEW versioned prompt | Structured understanding; `is_issue_candidate` |
| Match | NEW versioned prompt | NEW / UPDATE / REJECT + confidence/reason |
| Structuring | Evolve `SIGNAL_ANALYSIS_PROMPT` / `issue_card_v*` | Title, summary, participation block, soft `is_trending` |

Do **not** send all raw_items to any stage. Caps in Settings.

Heuristic fallback if no API key: degrade; do not invent facts.

---

## Evidence Aggregation

Before Structuring, attach representative RawItems / URLs with trust tiers:

`OFFICIAL | NEWS | SOCIAL | COMMUNITY | UNKNOWN`

Reuse `signal_sources`. Prefer multi-source Issues; single-source allowed but Quality Gate may down-rank or require stronger novelty.

---

## Participation

Optional. Remove `topic_needs_participation` hard reject.  
`participation_suitable=false` → read-only card.

---

## Trending

Attribute after Issue exists: LLM suggestion AND deterministic heat evidence.  
**Not** a create gate. Low-reply new events still eligible (Case E).

---

## Quality Gate (MVP)

Deterministic + existing LLM output validation:

- title/summary non-empty
- schema valid
- ≥1 evidence source when published
- number grounding (`quality.py`)
- participation options coherent if suitable
- daily soft cap / diversity (`publish_quota` retargeted)

**No** second LLM judge in MVP (Phase 2 candidate).
