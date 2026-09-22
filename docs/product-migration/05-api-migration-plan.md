# 05 — API Migration Plan

## Strategy

1. **Additive first**: new `/api/v1/issues*` alongside existing `/signals*`
2. Thin adapter: Issue list can read published Signals until schema migrates
3. Deprecate finance-only endpoints after UI cutover
4. Never break device register / settings / cost / push mid-migration

## Proposed Issue APIs (MVP)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/issues` | Feed (sort=trending\|rising\|new) |
| GET | `/issues/{id}` | Detail + options + aggregates |
| POST | `/issues/{id}/participate` | Cast/change vote |
| GET | `/issues/{id}/participation` | My vote + counts |
| GET | `/issues/{id}/comments` | List |
| POST | `/issues/{id}/comments` | Create |
| POST | `/issues/{id}/comments/{cid}/like` | Optional |
| POST | `/issues/{id}/events` | impression/open analytics (or beacon) |

Reuse query param `user_id` / device session pattern from existing APIs until real auth.

## Existing APIs

| API | Plan |
| --- | --- |
| `GET /signals`, `GET /signals/{id}` | Keep during migrate; alias or proxy to Issues |
| `POST /signals/{id}/explain*` | Keep; retarget to Issue context later |
| `/watchlist`, `/assets` | Keep; hide from primary nav |
| `/brief` | Keep backend; hide Home hero |
| `/calendar` | Keep; defer UI tab |
| `/settings`, `/push`, `/billing`, `/cost` | KEEP |

## Response shape (sketch)

```json
{
  "id": "...",
  "title": "...",
  "summary": "...",
  "why_it_matters": "...",
  "key_points": ["..."],
  "category": "Technology",
  "topic": "ai-chips",
  "trend_score": 0.82,
  "participation_type": "binary",
  "participation_question": "Blackwell 수요가 계속 강할까?",
  "options": [{"id": "...", "label": "계속 강할 것 같다"}, {"id": "...", "label": "둔화될 것 같다"}],
  "participation_count": 1824,
  "option_counts": {"optA": 1100, "optB": 724},
  "source_count": 12,
  "sources": [{"provider": "x", "url": "..."}],
  "my_option_id": null
}
```

## Compatibility

- Frontend switches clients screen-by-screen
- Mobile Flutter later consumes same Issue API
- Old Signal DTOs remain for rollback ~1 release
