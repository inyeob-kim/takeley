#!/usr/bin/env bash
# Step 7 smoke checks against production (or local).
set -euo pipefail

API_BASE="${1:-http://127.0.0.1:8000}"
ADMIN_ORIGIN="${2:-}"

echo "== Health: $API_BASE/health =="
curl -fsS --max-time 15 "$API_BASE/health" | tee /tmp/takeley-health.json
echo

echo "== OpenAPI =="
curl -fsS --max-time 15 -o /dev/null -w "openapi:%{http_code}\n" "$API_BASE/openapi.json"

echo "== Issues list =="
curl -fsS --max-time 30 -o /tmp/takeley-issues.json -w "issues:%{http_code}\n" \
  "$API_BASE/api/v1/issues?limit=5&sort=trending"
python3 - <<'PY'
import json
from pathlib import Path
p = Path("/tmp/takeley-issues.json")
data = json.loads(p.read_text() or "{}")
items = data.get("items") or data.get("issues") or []
print(f"issue_count={len(items)}")
PY

if [[ -n "$ADMIN_ORIGIN" ]]; then
  echo "== Admin origin =="
  curl -fsS --max-time 15 -o /dev/null -w "admin:%{http_code}\n" "$ADMIN_ORIGIN/" || true
fi

echo "OK: smoke finished for $API_BASE"
