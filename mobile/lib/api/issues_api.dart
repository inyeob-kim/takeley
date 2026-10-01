import 'api_client.dart';
import 'models.dart';

class IssuesApi {
  IssuesApi(this._api);

  final ApiClient _api;

  Map<String, String> _userQuery(String? userId) {
    if (userId == null || userId.isEmpty) return const {};
    return {'user_id': userId};
  }

  Future<({List<Issue> items, int count})> fetchIssues({
    int limit = 30,
    String sort = 'trending',
    String? category,
    String contentKind = 'ISSUE',
    String? userId,
  }) async {
    final query = <String, String>{
      'limit': '$limit',
      'sort': sort,
      'content_kind': contentKind,
      if (category != null && category.isNotEmpty) 'category': category,
      ..._userQuery(userId),
    };
    final data = await _api.getJson('/api/v1/issues', query: query);
    final raw = data['items'];
    final items = raw is List
        ? raw
            .whereType<Map>()
            .map((e) => Issue.fromJson(Map<String, dynamic>.from(e)))
            .toList()
        : <Issue>[];
    final count = (data['count'] as num?)?.toInt() ?? items.length;
    return (items: items, count: count);
  }

  Future<Issue> fetchIssue(String id, {String? userId}) async {
    final data = await _api.getJson(
      '/api/v1/issues/${Uri.encodeComponent(id)}',
      query: _userQuery(userId),
    );
    return Issue.fromJson(data);
  }

  Future<Issue> participate({
    required String id,
    required String optionId,
    String? userId,
    String? note,
  }) async {
    final data = await _api.postJson(
      '/api/v1/issues/${Uri.encodeComponent(id)}/participate',
      {
        'option_id': optionId,
        if (userId != null) 'user_id': userId,
        if (note != null) 'note': note,
      },
      query: _userQuery(userId),
    );
    // Participate returns partial — caller merges onto existing Issue.
    return Issue.fromJson({
      'id': data['issue_id'] ?? id,
      'title': '',
      'summary': '',
      ...data,
    });
  }

  Future<Map<String, dynamic>> participateRaw({
    required String id,
    required String optionId,
    String? userId,
    String? note,
  }) {
    return _api.postJson(
      '/api/v1/issues/${Uri.encodeComponent(id)}/participate',
      {
        'option_id': optionId,
        if (userId != null) 'user_id': userId,
        if (note != null) 'note': note,
      },
      query: _userQuery(userId),
    );
  }

  Future<Map<String, dynamic>?> fetchOtherTake({
    required String id,
    String? userId,
  }) async {
    final data = await _api.getJson(
      '/api/v1/issues/${Uri.encodeComponent(id)}/other-take',
      query: _userQuery(userId),
    );
    final item = data['item'];
    if (item is Map) {
      return Map<String, dynamic>.from(item);
    }
    return null;
  }

  Future<void> skipOtherTake({
    required String id,
    String? userId,
    String? exposureId,
  }) {
    return _api.postJson(
      '/api/v1/issues/${Uri.encodeComponent(id)}/other-take/skip',
      {
        if (userId != null) 'user_id': userId,
        if (exposureId != null) 'exposure_id': exposureId,
      },
      query: _userQuery(userId),
    );
  }

  Future<void> openOtherTake({
    required String id,
    String? userId,
    String? exposureId,
  }) {
    return _api.postJson(
      '/api/v1/issues/${Uri.encodeComponent(id)}/other-take/open',
      {
        if (userId != null) 'user_id': userId,
        if (exposureId != null) 'exposure_id': exposureId,
      },
      query: _userQuery(userId),
    );
  }

  Future<Issue> follow(String id, {String? userId}) async {
    final data = await _api.postJson(
      '/api/v1/issues/${Uri.encodeComponent(id)}/follow',
      {},
      query: _userQuery(userId),
    );
    return Issue.fromJson(data);
  }

  Future<Issue> unfollow(String id, {String? userId}) async {
    final data = await _api.deleteJson(
      '/api/v1/issues/${Uri.encodeComponent(id)}/follow',
      query: _userQuery(userId),
    );
    return Issue.fromJson(data);
  }

  Future<Issue> view(String id, {String? userId}) async {
    final data = await _api.postJson(
      '/api/v1/issues/${Uri.encodeComponent(id)}/view',
      {},
      query: _userQuery(userId),
    );
    return Issue.fromJson(data);
  }

  Future<List<IssueComment>> fetchComments(String id, {String? userId}) async {
    final data = await _api.getJson(
      '/api/v1/issues/${Uri.encodeComponent(id)}/comments',
      query: _userQuery(userId),
    );
    final raw = data['items'];
    if (raw is! List) return const [];
    return raw
        .whereType<Map>()
        .map((e) => IssueComment.fromJson(Map<String, dynamic>.from(e)))
        .toList();
  }

  Future<IssueComment> postComment({
    required String id,
    required String content,
    String? userId,
  }) async {
    final data = await _api.postJson(
      '/api/v1/issues/${Uri.encodeComponent(id)}/comments',
      {
        'content': content,
        if (userId != null) 'user_id': userId,
      },
      query: _userQuery(userId),
    );
    return IssueComment.fromJson(data);
  }

  Future<void> recordEvent({
    required String id,
    required String event,
    String? userId,
    String? shareId,
    String? refUserId,
    String? shareIntent,
  }) async {
    await _api.postJson(
      '/api/v1/issues/${Uri.encodeComponent(id)}/events',
      {
        'event': event,
        if (userId != null) 'user_id': userId,
        if (shareId != null && shareId.isNotEmpty) 'share_id': shareId,
        if (refUserId != null && refUserId.isNotEmpty) 'ref_user_id': refUserId,
        if (shareIntent != null && shareIntent.isNotEmpty)
          'share_intent': shareIntent,
      },
    );
  }

  Future<MyActivity> fetchMyActivity({String? userId}) async {
    final data = await _api.getJson(
      '/api/v1/issues/activity/me',
      query: _userQuery(userId),
    );
    return MyActivity.fromJson(data);
  }
}
