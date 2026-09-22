import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

import '../api/device_session.dart';
import '../api/push_api.dart';
import '../navigation/deep_link.dart';

typedef PushOpenCallback = void Function(DeepLinkTarget? target);

/// Registers FCM token (ios / android) with TAKELEY backend and handles taps.
/// Web FCM is not used in the Flutter app; consumer product is native.
class FcmService {
  FcmService({
    required DeviceSession session,
    required PushApi pushApi,
  })  : _session = session,
        _pushApi = pushApi;

  final DeviceSession _session;
  final PushApi _pushApi;
  PushOpenCallback? onOpened;
  bool ready = false;
  String? lastError;

  Future<void> initialize({bool requestPermission = true}) async {
    if (kIsWeb) {
      debugPrint('FcmService: skip native FCM on web');
      ready = false;
      return;
    }

    try {
      await Firebase.initializeApp();
    } catch (e) {
      lastError = '$e';
      debugPrint('FcmService: Firebase.initializeApp failed: $e');
      debugPrint(
        'Add google-services.json (Android) / GoogleService-Info.plist (iOS), then rebuild.',
      );
      rethrow;
    }

    final messaging = FirebaseMessaging.instance;

    await messaging.setForegroundNotificationPresentationOptions(
      alert: true,
      badge: true,
      sound: true,
    );

    if (requestPermission) {
      final settings = await messaging.requestPermission(
        alert: true,
        badge: true,
        sound: true,
        provisional: false,
      );
      if (settings.authorizationStatus == AuthorizationStatus.denied) {
        debugPrint('FcmService: notification permission denied');
        ready = false;
        return;
      }
    }

    if (defaultTargetPlatform == TargetPlatform.iOS) {
      final apns = await messaging.getAPNSToken();
      if (apns == null) {
        debugPrint('FcmService: waiting briefly for APNs token…');
        await Future<void>.delayed(const Duration(seconds: 2));
      }
    }

    final platform = platformName();
    await _session.ensureRegistered(platform: platform);
    await _registerCurrentToken(messaging, platform);

    messaging.onTokenRefresh.listen((token) {
      _pushApi.registerToken(
        fcmToken: token,
        platform: platform,
        userId: _session.userId,
        deviceId: _session.deviceId,
        clientDeviceId: _session.deviceId,
      );
    });

    FirebaseMessaging.onMessage.listen((message) {
      debugPrint(
        'FcmService: foreground message '
        'title=${message.notification?.title} data=${message.data}',
      );
    });

    FirebaseMessaging.onMessageOpenedApp.listen((message) {
      onOpened?.call(parsePushData(message.data));
    });

    final initial = await messaging.getInitialMessage();
    if (initial != null) {
      onOpened?.call(parsePushData(initial.data));
    }

    ready = true;
  }

  Future<bool> requestAndRegister() async {
    try {
      await initialize(requestPermission: true);
      return ready;
    } catch (_) {
      return false;
    }
  }

  Future<void> _registerCurrentToken(
    FirebaseMessaging messaging,
    String platform,
  ) async {
    final token = await messaging.getToken();
    if (token == null || token.isEmpty) {
      debugPrint('FcmService: empty FCM token (check Firebase + APNs setup)');
      return;
    }
    await _pushApi.registerToken(
      fcmToken: token,
      platform: platform,
      userId: _session.userId,
      deviceId: _session.deviceId,
      clientDeviceId: _session.deviceId,
    );
    debugPrint('FcmService: $platform token registered (${token.length} chars)');
  }

  static String platformName() {
    if (kIsWeb) return 'web';
    switch (defaultTargetPlatform) {
      case TargetPlatform.iOS:
        return 'ios';
      case TargetPlatform.android:
        return 'android';
      default:
        return 'web';
    }
  }
}

@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp();
}
