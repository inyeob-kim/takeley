# TAKELEY native push (iOS / Android)

Web push already works in the browser. **Phone OS notifications** need the Flutter
app in `mobile/` with Firebase **iOS + Android** apps in the **same** Firebase
project that the backend service account uses.

Backend send path already includes:

- `AndroidConfig(priority=high)`
- `APNSConfig` (sound + priority)

Once an `ios` / `android` device token is registered via
`POST /api/v1/push/devices/register`, the worker delivers to that token the same
way it does for `web`.

---

## Package IDs (TAKELEY)

| Platform | ID |
|----------|-----|
| Android `applicationId` / namespace | `com.takeley.app` |
| iOS Bundle ID | `com.takeley.app` |

Custom URL scheme (share CTA): `takeley://i/{issueId}?sid=&ref=`

---

## 1. Firebase Console

1. Open the same project as web (the one behind `firebase-credentials.json`) — project **`takeley`**.
2. **Add app → Android**
   - Package name: **`com.takeley.app`**
   - Download `google-services.json` → `mobile/android/app/google-services.json` (gitignored).
3. **Add app → iOS**
   - Bundle ID: **`com.takeley.app`**
   - Download `GoogleService-Info.plist` → `mobile/ios/Runner/GoogleService-Info.plist` (gitignored).
   - Do **not** commit a placeholder plist; use the real file from Firebase only.
4. **iOS APNs (required or iOS tokens stay empty)**
   - Apple Developer → Keys → Apple Push Notifications service (APNs).
   - Firebase → Project settings → Cloud Messaging → Apple app configuration
     → upload APNs auth key (or certificates).

---

## 2. iOS project wiring (already in repo)

- `Runner/AppDelegate.swift` — remote notification registration + UNUserNotificationCenter delegate
- `Runner/Runner.entitlements` — `aps-environment` = `development` (change to `production` for App Store builds)
- `Info.plist` — `UIBackgroundModes` includes `remote-notification`; `CFBundleURLTypes` includes `takeley`
- Xcode target uses `CODE_SIGN_ENTITLEMENTS = Runner/Runner.entitlements`

After adding `GoogleService-Info.plist`, open `ios/Runner.xcworkspace` once in Xcode and confirm Push Notifications capability is on (entitlements file should show).

---

## 3. Run on a real device

Emulators often cannot receive real push reliably (esp. iOS).

```bash
cd mobile
flutter pub get

# Android
flutter run -d <android-id> --dart-define=API_BASE_URL=http://<your-lan-ip>:8000

# iOS physical device
flutter run -d <ios-id> --dart-define=API_BASE_URL=http://<your-lan-ip>:8000
```

Phone and PC must reach the API (`API_BASE_URL`). `127.0.0.1` on a phone is the
phone itself — use your computer’s LAN IP for local backend.

Allow notifications when prompted.

### Share deep link smoke test (Android)

With the app installed:

```bash
adb shell am start -a android.intent.action.VIEW -d "takeley://i/<ISSUE_ID>?sid=test"
```

App should open Issue detail and record `shared_link_opened` when `sid` is present.

---

## 4. Verify token registration

After the app shows “네이티브 푸시 준비됨”, check backend for a device token with
`platform` = `ios` or `android`.

Then publish an Issue from Admin. Worker `send_push` should deliver.

---

## 5. Checklist

| Item | Android | iOS |
|------|---------|-----|
| `google-services.json` / `GoogleService-Info.plist` | Required | Required |
| APNs key in Firebase | — | Required |
| Notification permission | Android 13+ prompt | System prompt |
| Physical device recommended | Yes | **Yes** |
| Backend `FCM_ENABLED=true` + credentials | Same for both | Same |
| `takeley://` URL scheme | intent-filter | CFBundleURLTypes |

---

## 6. Share landing (web)

HTTPS `/i/{id}` serves a **readable** page (title / summary / cover). Participation
CTA opens `takeley://`; if the app is missing, store URLs from
`PUBLIC_ANDROID_STORE_URL` / `PUBLIC_IOS_STORE_URL` (optional) are shown.
