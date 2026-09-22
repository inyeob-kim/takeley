import 'api_client.dart';
import 'models.dart';

class SettingsApi {
  SettingsApi(this._api);

  final ApiClient _api;

  Future<UserSettings> fetch({String? userId}) async {
    final data = await _api.getJson(
      '/api/v1/settings',
      query: {
        if (userId != null && userId.isNotEmpty) 'user_id': userId,
      },
    );
    return UserSettings.fromJson(data);
  }

  Future<UserSettings> update({
    required String? userId,
    bool? notificationsEnabled,
    String? displayName,
    String? briefAlarmTime,
    String? timezone,
    String? ttsVoiceGender,
  }) async {
    final body = <String, dynamic>{
      if (notificationsEnabled != null)
        'notifications_enabled': notificationsEnabled,
      if (displayName != null) 'display_name': displayName,
      if (briefAlarmTime != null) 'brief_alarm_time': briefAlarmTime,
      if (timezone != null) 'timezone': timezone,
      if (ttsVoiceGender != null) 'tts_voice_gender': ttsVoiceGender,
    };
    final data = await _api.patchJson(
      '/api/v1/settings',
      body,
      query: {
        if (userId != null && userId.isNotEmpty) 'user_id': userId,
      },
    );
    return UserSettings.fromJson(data);
  }
}
