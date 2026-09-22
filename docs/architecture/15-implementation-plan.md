# 15 — Implementation Plan (final, LLM-first)

Supersedes earlier Sprint plans that made entity/time the semantic judge.  
Cursor plan: `issue_pipeline_redesign_a5120cc9.plan.md`.

```text
Sprint0 hygiene
 → Sprint1 broad discovery (heat≠Issue gate)
 → Sprint2 candidate + LLM Understanding
 → Sprint3 LLM Match + Golden A–E
 → Sprint4 evidence + structuring + quality gate + publish
 → Sprint5 metrics / schedule / snapshots (no velocity/embed)
```

Each sprint behind feature flags; default preserves today’s behavior until enabled.

### Out of this migration

- Embedding clustering  
- Dynamic query generation  
- Velocity scoring (needs snapshots first)  
- Second LLM quality judge  
- `issues` table rename  
- Deleting Brief/TTS/calendar/watchlist/ticker search code  

### Success question

> Can AI understand differently worded sources, merge same events, split different events, update instead of duplicating, and ship readable optionally participatory Issue Cards?
