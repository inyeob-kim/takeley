# 12 — API Migration (TAKELEY)

## Primary Issue API (KEEP contract)

`backend/app/api/v1/issues.py` + `issue_service.py`:

| Endpoint | Role |
| --- | --- |
| `GET /api/v1/issues` | Feed (`sort`, category chips) |
| `GET /api/v1/issues/{id}` | Detail + options + my take |
| `POST .../participate` | Upsert take (vote) |
| `GET/POST .../comments` | Flat comments |
| `POST .../follow` · `DELETE .../follow` | Issue follow |
| `POST .../view` | Detail seen / retention |
| `POST .../events` | impression / open / funnel |
| `GET /issues/activity/me` | My takes + follows + comments |

Routers stay thin; services personalize lightly; **no LLM on request path**.

DB rows come from table **`issues`**.

---

## Additive response fields

| Field | Purpose |
| --- | --- |
| `is_following`, `has_new_update`, `my_last_seen_at` | Retention |
| `lifecycle` / `trend_status` | Badges |
| `source_count` | Social proof |

---

## Signals API (legacy)

`/api/v1/signals*` — DEFER / ops / rollback. Home uses **Issues** only.

---

## Compatibility

- Clients must use `/issues*` for TAKELEY Home / Detail / Activity.
- Internal ORM may expose `Issue` with temporary `Signal` alias.
