import 'api_client.dart';

class SafetyApi {
  SafetyApi(this._api);

  final ApiClient _api;

  Map<String, String> _userQuery(String? userId) {
    if (userId == null || userId.isEmpty) return const {};
    return {'user_id': userId};
  }

  Future<void> report({
    required String targetType,
    required String targetId,
    required String reason,
    String? userId,
  }) async {
    await _api.postJson(
      '/api/v1/safety/report',
      {
        'target_type': targetType,
        'target_id': targetId,
        'reason': reason,
        if (userId != null) 'user_id': userId,
      },
      query: _userQuery(userId),
    );
  }

  Future<void> hide({
    required String targetType,
    required String targetId,
    String? userId,
  }) async {
    await _api.postJson(
      '/api/v1/safety/hide',
      {
        'target_type': targetType,
        'target_id': targetId,
        if (userId != null) 'user_id': userId,
      },
      query: _userQuery(userId),
    );
  }

  Future<void> blockUser({
    required String blockedUserId,
    String? userId,
  }) async {
    await _api.postJson(
      '/api/v1/safety/block',
      {
        'blocked_user_id': blockedUserId,
        if (userId != null) 'user_id': userId,
      },
      query: _userQuery(userId),
    );
  }

  Future<void> deleteComment({
    required String commentId,
    String? userId,
  }) async {
    await _api.deleteJson(
      '/api/v1/safety/comments/${Uri.encodeComponent(commentId)}',
      query: _userQuery(userId),
    );
  }
}
