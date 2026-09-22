# 07 — AI Pipeline Plan

## Target funnel (preserve cost structure)

```text
Sources (X, News, RSS, Web, …)
        ↓
Normalize + cheap filter
        ↓
Dedupe / similarity
        ↓
Cluster (same issue?)
        ↓
LLM on clusters only  ← shared, not per-user
        ↓
Issue JSON (facts + argument + participation?)
        ↓
Quality gate + daily Issue cap
        ↓
DB → Feed → Participation (no LLM)
```

## What changes in the LLM job

| Old question | New question |
| --- | --- |
| Is this investor-relevant US market news? | What single issue are people paying attention to? |
| Write finance Signal fields | Write Issue card + optional participation |
| related_symbols required vibe | topic/category; assets optional |
| Always publishable if important | Skip or no-vote if no natural debate |

## Prompt modules (MODIFY, don’t fork blindly)

- Evolve `SIGNAL_ANALYSIS_PROMPT` → `ISSUE_ANALYSIS_PROMPT` (version bump)
- Output schema adds: `category`, `topic`, `participation_suitable`, `participation_type`, `participation_question`, `participation_options[]`
- Keep: no invented facts; separate fact vs opinion; no tipster calls
- Soften finance-only Korean investor persona toward general “curious adult” (can keep calm ~해요 tone)

## Participation quality rules

1. Never invent controversy for product colors / pure announcements  
2. Options ≤ 4, short labels  
3. Prediction type = opinion outlook only (no money)  
4. If unsuitable → `participation_suitable=false`  

## Clustering guidance

Reuse `cluster.py`; later tune similarity toward **topic/event** not ticker co-occurrence only.

## Comment summary (post-MVP architecture)

Worker job when `comment_count >= threshold`: summarize stances → cache on Issue. No per-open LLM.

## Explain / Ask AI

Keep as optional detail tool; daily cap remains. Not required for MVP loop.
