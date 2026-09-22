# 02 — KEEP / MODIFY / REMOVE

> File-path linked. Prefer reuse over rewrite. REMOVE means “stop shipping in MVP,” not “delete git history tomorrow.”

Legend: **KEEP** = reuse as-is or with thin adapters · **MODIFY** = keep core, change contract/UX · **REMOVE/DEFER** = out of MVP or park behind flags

---

## KEEP (reuse aggressively)

| Capability | Paths | Why |
| --- | --- | --- |
| Provider interface | `backend/app/providers/base.py` | Multi-source → Common ingestion |
| X provider | `backend/app/providers/x_provider.py` | Primary social firehose for Issue discovery |
| News + article body | `news_provider.py`, `article_fetch.py` | Corroboration + longer context |
| Reddit / Official / Calendar / DART / Symbol | respective `providers/*` | Optional sources; calendar can seed Topics later |
| Ingest job + cursors | `worker/jobs/ingest.py`, `db` `IngestCursor` | Proven polling / budget / rotation |
| Cheap filter | `pipeline/cheap_filter.py` | Cost funnel stage 1 |
| Normalize / fingerprint | `pipeline/normalize.py` | Dedupe + keep gates (macro keywords reusable) |
| Cluster | `pipeline/cluster.py` | Multi-source → one topic blob |
| Dedupe helpers | `pipeline/dedupe.py` | Shared intelligence hygiene |
| Analyze infrastructure | `pipeline/analyze.py`, `prompts.py` | Swap prompt goal Signal→Issue; keep JSON+fallback |
| Classification / quality | `classification.py`, `quality.py`, `classify.py` | Tipster/promo exclusion still useful |
| Publish quota pattern | `pipeline/publish_quota.py`, settings caps | Becomes daily Issue cap |
| Usage + cost | `core/usage.py`, `services/cost_service.py`, `api/v1/cost.py` | Non-negotiable observability |
| Config / Settings | `core/config.py`, `.env` | Knobs stay env-driven |
| DB session / repos pattern | `db/session.py`, `db/repositories/` | Persistence layer |
| Device user + prefs | `device_service.py`, `preference_service.py`, `api/v1/settings.py` | Lightweight identity for participation |
| Push plumbing | `push_*` services, `api/v1/push.py`, `worker/jobs/send_push.py` | Issue alerts later; keep infra |
| Entitlement / billing shell | `entitlement_service.py`, `api/v1/billing.py` | Pro gate later |
| React API client pattern | `frontend/src/api/httpClient.ts`, `*Api.ts`, `mappers.ts` | Extend for Issue APIs |
| Design system / senior UI tone | `.cursor/rules/design-system.mdc`, shared components | Calm cards fit Issue UX |
| Tests as assets | `backend/tests/*` | Migrate assertions; don’t trash wholesale |
| Flutter FCM scaffold | `mobile/lib/**` | Keep for push when Flutter UI arrives |

---

## MODIFY (core reusable, contract changes)

| Capability | Paths | Change direction |
| --- | --- | --- |
| **Signal → Issue domain** | `domain/models.py` `MarketSignal`; `db.models.Signal`; `schemas.SignalOut` | Rename/extend: category, topic, participation_question/options, trend_score; loosen finance-only fields |
| **Signal generation job** | `worker/jobs/process_signals.py` | Same funnel; output Issue; optional participation generation step |
| **Analyze prompts** | `pipeline/prompts.py` `SIGNAL_ANALYSIS_*` | Goal: “what are people debating?” + suitable participation type (not forced binary) |
| **Entities / sectors** | `pipeline/entities.py` | Topic/category extract; assets optional (`related_assets`) |
| **Universe / monitor** | `services/universe.py` | From stock monitor → **topic seeds + source budgets**; stocks optional overlay |
| **Signal service / API** | `services/signal_service.py`, `api/v1/signals.py` | Evolve to Issue feed + detail; keep explain as “Ask AI about this Issue” |
| **Personalization** | `services/personalization.py` | Watchlist boost → later Topic follows; MVP: trending + recency |
| **Brief / TTS** | `brief_service.py`, `brief_synthesize.py`, `select_signals.py`, `pipeline/tts.py`, `worker/jobs/generate_brief.py`, `api/v1/brief.py` | **Defer in MVP UI**; optionally reframe as “today’s Issues audio”; code kept, feature-flag off or low priority |
| **Home UI** | `frontend/src/screens/HomeScreen.tsx` | Brief-first → **Issue Feed** (trending / rising) |
| **Signal list/detail UI** | `SignalListRow.tsx`, `SignalDetailScreen.tsx`, `TodaySignalsScreen.tsx` | → Issue Card / Issue Detail + participation + comments |
| **Nav** | `App.tsx` | Tabs: Home / Explore? / My Activity / Settings (drop finance calendar as primary) |
| **Daily cap** | `daily_signal_cap`, hard ceiling | → `daily_issue_cap` (still ~5–10 quality Issues) |
| **Push copy** | `push_template_service.py` | Signal new → Issue new / participation reminder |
| **Ask AI explain** | `explain_service.py`, detail sheet | Keep as Issue-context explain; not core MVP path |
| **Asset kind TOPIC** | `domain` `AssetKind.TOPIC` already exists | Seed for future Topic follow without new invent |

---

## REMOVE / DEFER (out of MVP core)

| Capability | Paths | Decision | Why |
| --- | --- | --- | --- |
| Finance calendar as primary tab | `api/v1/calendar.py`, `CalendarScreen.tsx`, `sync_calendar.py` | **DEFER** | Useful as source/context later; not Issue participation core |
| Stock watchlist as primary nav | `watchlist.py` API + screens | **DEFER / MODIFY later** | Stock-centric; evolve to Topic follow post-MVP |
| Asset search as hero | `assets.py`, `symbol_provider.py` | **DEFER** | Keep for related assets on finance Issues |
| Market reaction / rise-fall emphasis as required UX | Signal emphasis UI | **DEFER** | Optional for finance Issues only |
| Tipster-heavy finance classification as product identity | quality/classify | **KEEP infra, soften product copy** | Still filter junk |
| TTS player as Home hero | `AudioPlayerScreen.tsx`, brief card | **DEFER** | Read → participate first |
| Full Flutter product UI rewrite now | `mobile/` | **DEFER** | Scaffold only; React is current shell |
| Social graph (follow, DM, friends) | — | **REMOVE from MVP** | Explicitly out of scope |
| Prediction markets / money / points | — | **REMOVE from MVP** | Explicitly out of scope |
| Dual Korean equity path as MVP | DART / `kr_news` | **DEFER** | Keep code; not Issue MVP |
| Hard stock-coupled Issue model | `related_symbols` required | **MODIFY away** | Optional related assets only |

**Do not delete** deferred modules in Phase 1–4. Prefer feature flags / hide nav / stop scheduling jobs.

---

## Classification summary

```text
KEEP ........ ingestion, LLM funnel, cost, device/push, clustering, quotas
MODIFY ...... Signal→Issue, prompts, Home/Detail UI, ranking, caps naming
DEFER ....... brief/TTS hero, calendar tab, stock watchlist, Flutter UI, KR path
OUT ......... social network, prediction market, gamification economy
```
