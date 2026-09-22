# TAKELEY

**Take a look. Take a side.** · 테이클리 (TAKE + DAILY)

---

## 실행 (매일 쓰는 것)

터미널 **3개** (또는 백엔드+워커+앱).

### 1) API

```bash
cd backend
.\.venv\Scripts\activate          # 최초 1회: py -3.12 -m venv .venv && pip install -r requirements.txt
uvicorn app.main:app --reload
# → http://127.0.0.1:8000
```

### 2) Worker (ingest / 푸시 등)

```bash
cd backend
.\.venv\Scripts\activate
python -m worker.main
```

### 3) Flutter 앱

```bash
cd mobile
flutter pub get                   # 의존성 바뀌었을 때만
# PC / iOS 시뮬
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000
# Android 에뮬 (에뮬 → PC API)
flutter run -d emulator-5554 --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

### 4) Admin (필요할 때만)

```bash
cd admin
npm install                       # 최초/락파일 변경 시
npm run dev
# → http://127.0.0.1:5174
```

**공유 링크:** `http://127.0.0.1:8000/i/{이슈ID}?sid=...`  
**푸시 설정:** `mobile/PUSH_NATIVE.md`

---

## Structure

```text
backend/   FastAPI + worker + /i/:id share landing
mobile/    Flutter (제품 앱)
admin/     Issue 검수·발행
docs/      설계 메모
```

## Setup (처음 한 번)

```bash
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Firebase 쓰면 firebase-credentials.json 넣고 FCM_ENABLED=true

cd ../mobile
flutter pub get
# google-services.json → mobile/android/app/
```

## Design principles

- Common intelligence first — API는 외부 소스/LLM 직접 호출 안 함
- 사용자 단위는 **Issue** (`signals` 테이블)
- Loop: Discover → Understand → Take → Return
