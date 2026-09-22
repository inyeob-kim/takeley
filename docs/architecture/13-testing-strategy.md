# 13 — Testing Strategy (revised)

## Golden semantic tests (blocking for Sprint 3+)

| ID | Scenario | Expect |
| --- | --- | --- |
| A | Same event, 3 paraphrases (Blackwell demand) | 1 Issue |
| B | Same entity, different events (demand vs Ultra announce) | 2 Issues |
| C | X + News + Official same story | 1 Issue |
| D | Pure personal opinion | REJECT / no new Issue |
| E | Genuine new event, low replies | Not hard-dropped at discovery/candidate |

Fixture location (when implementing): `backend/tests/fixtures/issues/`.

---

## Other layers

| Layer | Focus |
| --- | --- |
| Ingest | cursors, flags, pool cap, no has:replies hard-block when split on |
| Candidate | priority ordering; never “meaning reject” via heat alone |
| Understanding | schema parse; opinion → not candidate |
| Match | Golden A–E |
| Quality gate | empty title reject; grounding |
| API | feed filter; read-only + participate |
| Cost | understand/match/structure call counts ≤ budgets |

Entity/time/keyword tests may assert **shortlist behavior**, never final merge correctness.
