# 10 — MVP Scope + Implementation Order

## In MVP

- Shared ingest (X + News at minimum)
- Cluster → Issue LLM (with participation optional)
- Daily quality Issue cap (~5–10)
- Issue Feed Home
- Issue Card + Detail
- Participate (one vote / user)
- Comments (flat) + basic like
- Impression/open/participation metrics hooks
- Device user + settings + cost tracking
- Hide (not delete): brief hero, calendar tab, watchlist tab

## Out of MVP (explicit)

- Follow/DM/friends, points, money, prediction markets, reputation
- Topic follow (design-ready via AssetKind.TOPIC later)
- AI comment summary
- Flutter full UI
- Forced debate on every item
- Chart/HTS/portal features

## Implementation order (after plan approval)

1. **DB additive** — options / participations / comments (+ Issue columns)  
2. **Issue API** — list/detail/participate/comments (adapter over signals OK)  
3. **Pipeline prompt MODIFY** — Issue schema + participation_suitable  
4. **Quota rename/tune** — daily Issue cap  
5. **React Home + Card + Detail** — participation UI  
6. **Metrics events** — participation rate  
7. **Hide finance-primary nav** — feature flags  
8. **Calibrate AI** — quality of questions (no forced binary)  
9. **Cleanup** — only after metrics prove loop  

## Migration risks

| Risk | Mitigation |
| --- | --- |
| Breaking existing Signal clients | Dual API; adapter |
| LLM invents fake debates | `participation_suitable` + prompt rules + QA |
| Cost explosion from broader ingest | Keep cheap_filter + hard Issue ceiling |
| Empty feed during transition | Backfill read-only Issues from Signals |
| Over-deleting finance code | DEFER flags, not rm |
| Flutter assumed complete | Document React as current UI |
| Watchlist users feel abandoned | Messaging + later Topic follow |

## Definition of done (MVP)

A user can open the app, understand an Issue card in seconds, tap an opinion, see aggregate results, and optionally comment — without a finance dashboard.
