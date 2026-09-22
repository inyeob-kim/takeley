# 06 — UI Migration Plan

## Reality check

- **Current shippable UI:** React `frontend/`
- **Flutter `mobile/`:** FCM scaffold only — do not treat as full screen inventory
- Target product remains Flutter long-term; migrate React first as prototype, then port patterns

## Current nav (`App.tsx`)

`home | watchlist | calendar | settings` + overlays: signal detail, audio player, list expanders

## Target MVP nav

```text
Home (Issue Feed)
My Activity (my votes + comments)   -- can start as Settings subsection
Settings
```

Optional later: Explore (categories). Calendar / Watchlist: remove from primary tabs (Settings “실험실” or hide).

## Screen mapping

| Current | New | Action |
| --- | --- | --- |
| `HomeScreen` brief hero + signal preview | Issue Feed (뜨는 / 급상승) | MODIFY heavily |
| `SignalListRow` | `IssueCard` | MODIFY |
| `SignalDetailScreen` + Ask AI | Issue Detail: summary, points, sources, vote, results, comments | MODIFY; Ask AI DEFER secondary |
| `TodaySignalsScreen` | “전체 이슈” list | MODIFY |
| `AudioPlayerScreen` | Hidden / Settings flag | DEFER |
| `Watchlist*` | Hidden; later Topic follow | DEFER |
| `CalendarScreen` | Hidden | DEFER |
| `SettingsScreen` | Keep alarm/voice/push; add “내 참여” link | MODIFY lightly |

## Issue Card (MVP)

```text
[Category]
TITLE
짧은 요약
왜 중요한가? (1–2 lines)
• key points (≤3)
당신의 생각은?
[ Option A ] [ Option B ]
N명 참여
```

Calm senior-friendly UI rules still apply (large type, few actions, teal accent).

## Issue Detail order

1. Title  
2. Summary  
3. Key points  
4. Why it matters  
5. Sources (count + list)  
6. Question + options + live results  
7. Comments  
8. (Later) AI comment summary when N large  

## Design constraints

- No dashboard clutter, no chart stacks
- One primary CTA: participate
- Empty/error states calm
- Do not force binary UI when Issue has no participation
