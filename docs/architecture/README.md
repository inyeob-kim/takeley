# TAKELEY — Ingestion / Issue Pipeline

**Brand:** TAKELEY · *Take a look. Take a side.*  
**Final principle:** Deterministic logic = cost/prefilter only. **LLM = semantic decision maker** (understanding, same-Issue, NEW/UPDATE/REJECT, card + participation). Embedding / Dynamic Query / Velocity = Phase B.

User-facing unit = **Issue**. Physical store = **`issues`** table (ex-`signals`).

| Doc | Topic |
| --- | --- |
| [01-current-pipeline.md](01-current-pipeline.md) | Code audit |
| [02-pipeline-problems.md](02-pipeline-problems.md) | Hot-tweet ≠ Issue |
| [03-keep-modify-remove.md](03-keep-modify-remove.md) | Inventory |
| [04-new-ingestion-architecture.md](04-new-ingestion-architecture.md) | Source roles |
| [05-candidate-detection.md](05-candidate-detection.md) | Priority pool, not meaning |
| [06-clustering-strategy.md](06-clustering-strategy.md) | LLM Match is final |
| [07-issue-domain-model.md](07-issue-domain-model.md) | Domain + `issues` store |
| [08-issue-generation-pipeline.md](08-issue-generation-pipeline.md) | Full funnel |
| [09-fetch-scheduling.md](09-fetch-scheduling.md) | Lanes |
| [10-cost-impact.md](10-cost-impact.md) | X / LLM (3-stage) |
| [11-database-migration.md](11-database-migration.md) | Additive + rename |
| [12-api-migration.md](12-api-migration.md) | `/issues*` primary |
| [13-testing-strategy.md](13-testing-strategy.md) | Golden A–E |
| [14-mvp-scope.md](14-mvp-scope.md) | In / out |
| [15-implementation-plan.md](15-implementation-plan.md) | Sprint 0–5 |
| [16-metrics-and-observability.md](16-metrics-and-observability.md) | Funnel counters |
| [17-issue-lifecycle.md](17-issue-lifecycle.md) | MVP states |
| [18-llm-decision-model.md](18-llm-decision-model.md) | Decision boundary |

Core loop:

```text
DISCOVER → UNDERSTAND → TAKE → RETURN
```
