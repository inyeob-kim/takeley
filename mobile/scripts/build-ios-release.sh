#!/usr/bin/env bash
# App Store / TestFlight IPA with production API.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
flutter build ipa \
  --dart-define=API_BASE_URL=https://api.takeley.co \
  --dart-define=SHARE_ORIGIN=https://takeley.co \
  --build-name=1.0.0 \
  --build-number=3
echo "IPA: $ROOT/build/ios/ipa/takeley.ipa"
