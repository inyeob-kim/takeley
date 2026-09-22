# Issue Admin Portal

Separate review portal for draft Issues. Not part of the consumer app.

## Run

```bash
# API (backend/) — set ADMIN_API_KEY in .env
uvicorn app.main:app --reload

# Portal (admin/)
npm install
npm run dev
```

Open http://127.0.0.1:5174 and sign in with `ADMIN_API_KEY`.

## API

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/v1/admin/issues/counts` | draft / published / rejected |
| GET | `/api/v1/admin/issues?status=draft` | list |
| GET | `/api/v1/admin/issues/{id}` | detail + sources + column |
| POST | `/api/v1/admin/issues/{id}/publish` | draft → published (home feed) |
| POST | `/api/v1/admin/issues/{id}/reject` | draft → rejected |

Auth header: `X-Admin-Key: <ADMIN_API_KEY>`
