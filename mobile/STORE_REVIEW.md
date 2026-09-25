# App Store Connect — 제출 메모

Privacy URL: https://api.takeley.co/privacy  
Support URL: https://api.takeley.co/support  
Bundle ID: com.takeley.app  
Category: News  
Age: 18+ (Korea 19+)  
Build to upload: 1.0.0 (5)

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

## Guideline 1.2 reply (App Review에 붙여넣기)

TAKELEY now implements the UGC precautions in Guideline 1.2.

- Age rating is 18+. First launch requires the user to confirm they are 18+ and accept the EULA.
- EULA (in-app + https://takeley.co/terms) states there is no tolerance for objectionable content or abusive users.
- Comments are filtered for objectionable language before they are posted.
- Users can report a comment or deep-thought post, immediately hide it from their feed, and block the author.
- Users can delete their own comments so they leave the feed immediately.
- Reports appear in the operator admin queue. We review within 24 hours, remove violating content, and eject the user (account suspended; their posts are removed).
- In-app contact: Profile → Settings → 부적절한 활동 신고, or hello@takeley.co. Support page also explains the 24-hour process.

How to review: open an Issue, scroll to comments, tap ••• on a comment to report / hide / block. First launch shows the 18+ and terms gate.

## Build

```bash
cd mobile
./scripts/build-ios-release.sh
```

Upload `build/ios/ipa/takeley.ipa` in Transporter or Xcode Organizer.
