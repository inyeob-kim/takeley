import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_native_splash/flutter_native_splash.dart';
import 'package:flutter_web_plugins/url_strategy.dart';

import 'api/api_client.dart';
import 'api/device_session.dart';
import 'api/push_api.dart';
import 'app.dart';
import 'services/fcm_service.dart';

Future<void> main() async {
  final widgetsBinding = WidgetsFlutterBinding.ensureInitialized();
  FlutterNativeSplash.preserve(widgetsBinding: widgetsBinding);

  if (kIsWeb) {
    usePathUrlStrategy();
  }

  if (!kIsWeb) {
    FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);
  }

  final api = ApiClient();
  final session = DeviceSession(api);
  await session.hydrate();

  final fcm = FcmService(session: session, pushApi: PushApi(api));

  runApp(TakeleyApp(api: api, session: session, fcm: fcm));

  // Drop native splash once the first Flutter frame is ready.
  WidgetsBinding.instance.addPostFrameCallback((_) {
    FlutterNativeSplash.remove();
  });

  final platform = FcmService.platformName();
  try {
    await session
        .ensureRegistered(platform: platform)
        .timeout(const Duration(seconds: 8));
  } catch (e) {
    debugPrint('Device register failed/timed out: $e');
  }

  if (!kIsWeb) {
    fcm.initialize().catchError((Object e) {
      debugPrint('FCM init deferred failure: $e');
    });
  }
}
