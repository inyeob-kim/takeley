# 17 — Issue Lifecycle (MVP)

Store on `issues` (additive). Avoid overlapping states.

| State | Meaning | Enter | Exit |
| --- | --- | --- | --- |
| `CANDIDATE` | Understood / matched as NEW; not published | After Match=NEW pre-publish | Publish or reject |
| `PUBLISHED` | Live Issue Card | Quality gate pass | Update / stale / archive |
| `UPDATED` | New evidence merged; votes preserved | Match=UPDATE | Active feed still shows |
| `STALE` | No new evidence / low activity window | Scheduler or rules | Archive or revive on UPDATE |
| `ARCHIVED` | Hidden from Home | Manual/job | — |

`DISCOVERED` / `ACTIVE` omitted in MVP (overlap with CANDIDATE / PUBLISHED).

**Trending** is `trend_status`: `NORMAL | RISING | TRENDING` — orthogonal to lifecycle.
