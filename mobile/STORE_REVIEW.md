# App Store Connect — 제출 메모

Privacy URL: https://api.takeley.co/privacy  
Support URL: https://api.takeley.co/support  
Bundle ID: com.takeley.app  
Category: News  
Age: 12+

## Review notes (붙여넣기)

This app has no login. Identity is an anonymous device session.  
Open the home feed, tap an Issue, and leave a take (vote).  
Notifications are optional.  
Privacy policy: https://api.takeley.co/privacy  
To delete local data: Profile → Settings → 내 데이터 삭제.

## Privacy nutrition labels

- Device ID — App Functionality, not linked, not used for tracking  
- User Content (votes / comments) — App Functionality  
- No advertising, no tracking

## Export compliance

Uses only HTTPS (exempt encryption). Info.plist has ITSAppUsesNonExemptEncryption=false.

## Build

```bash
cd mobile
./scripts/build-ios-release.sh
```

Upload `build/ios/ipa/takeley.ipa` in Transporter or Xcode Organizer.
