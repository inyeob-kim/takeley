# 14 — MVP Scope (revised)

## In scope

1. Broad discovery + flags (`ISSUE_DISCOVERY_SPLIT_REPLIES`, `ISSUE_INGEST_FOCUS`)
2. Candidate priority pool (heat ≠ Issue create gate)
3. LLM Understanding + LLM Issue Match + LLM Structuring
4. Evidence aggregation + trust tier
5. Deterministic Quality Gate + Issue soft cap / diversity
6. Read-only Issues; optional participation
7. Funnel metrics; lifecycle MVP states
8. Use `issues` as Issue store; `/issues*` API

## Out of scope (Phase B / future)

- Embeddings as cluster judge
- Dynamic query generation
- Velocity scoring (until snapshots exist)
- Second LLM quality judge
- Renaming child FK columns (`signal_id` → `issue_id`)
- Deleting Brief / TTS / calendar / watchlist / ticker search code

## Success metric

Participation rate + Golden A–E pass rate — not “more Issues published.”
