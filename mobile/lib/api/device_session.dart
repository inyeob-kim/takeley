import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

import 'api_client.dart';

class DeviceSession {
  DeviceSession(this._api);

  static const _deviceKey = 'takeley_device_id_v1';
  static const _userKey = 'takeley_user_id_v1';

  final ApiClient _api;
  String? userId;
  String? deviceId;

  Future<void> hydrate() async {
    final prefs = await SharedPreferences.getInstance();
    deviceId = prefs.getString(_deviceKey);
    userId = prefs.getString(_userKey);
  }

  Future<void> ensureRegistered({
    required String platform,
    String? appVersion,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    var id = prefs.getString(_deviceKey);
    if (id == null || id.length < 8) {
      id = 'takeley-${const Uuid().v4()}';
      await prefs.setString(_deviceKey, id);
    }
    deviceId = id;

    final data = await _api.postJson('/api/v1/devices/register', {
      'device_id': id,
      'platform': platform,
      if (appVersion != null) 'app_version': appVersion,
    });
    final user = data['user'] as Map<String, dynamic>;
    userId = user['id'] as String;
    await prefs.setString(_userKey, userId!);
  }
}
