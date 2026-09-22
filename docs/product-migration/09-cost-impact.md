# 09 — Cost Impact

## Preserve

- `UsageEvent` recording for X / RSS / LLM / TTS / HTTP
- `cost_service` simulation + `/api/v1/cost`
- Caps: X search budget, explain cap, push cap
- Shared analyze (one cluster → one LLM call → many users)

## Cost shape after Issue product

| Stage | Expectation vs today |
| --- | --- |
| Ingest X/News | Similar or slightly higher if sources broaden beyond tickers |
| Clustering | Same order |
| LLM Issue gen | Similar to Signal analyze; **stricter daily Issue cap (5–10)** controls spend |
| Participation / comments | DB only — cheap |
| Comment summary LLM | Later; batch, thresholded |
| TTS / brief | Lower if deferred (savings) |
| Ask AI explain | Optional; keep daily cap |

## Risks

1. Broader non-ticker ingest → more raw → more clusters → more LLM unless cheap_filter + Issue cap tight  
2. Regenerating participation questions on edits → avoid; generate once at publish  
3. Per-user LLM for feed ranking — **forbid**; rank in DB  

## Controls to keep / rename

- `daily_signal_cap` → `daily_issue_cap` (behaviorally same soft pool)
- `daily_signal_hard_ceiling` → hard Issue ceiling
- `x_search_query_budget` + rotation — KEEP
- Macro theme keywords — KEEP as discovery aid (not finance-only)

## Success economically

High participation rate on few quality Issues beats many low-engagement Signals.
