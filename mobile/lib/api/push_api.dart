import 'api_client.dart';

class PushApi {
  PushApi(this._api);

  final ApiClient _api;

  Future<void> registerToken({
    required String fcmToken,
    required String platform,
    String? userId,
    String? deviceId,
    String? clientDeviceId,
    String? appVersion,
  }) async {
    await _api.postJson('/api/v1/push/devices/register', {
      'fcm_token': fcmToken,
      'platform': platform,
      if (userId != null) 'user_id': userId,
      if (deviceId != null) 'device_id': deviceId,
      if (clientDeviceId != null) 'client_device_id': clientDeviceId,
      if (appVersion != null) 'app_version': appVersion,
    });
  }
}
