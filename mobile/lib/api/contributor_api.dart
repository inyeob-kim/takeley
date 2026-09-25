import 'api_client.dart';

class ContributorMe {
  ContributorMe({
    required this.userId,
    required this.contributorStatus,
    this.displayName,
    this.application,
  });

  final String userId;
  final String contributorStatus;
  final String? displayName;
  final ContributorApplication? application;

  factory ContributorMe.fromJson(Map<String, dynamic> json) {
    final app = json['application'];
    return ContributorMe(
      userId: '${json['user_id'] ?? ''}',
      contributorStatus: '${json['contributor_status'] ?? 'NONE'}',
      displayName: json['display_name'] as String?,
      application: app is Map
          ? ContributorApplication.fromJson(Map<String, dynamic>.from(app))
          : null,
    );
  }
}

class ContributorApplication {
  ContributorApplication({
    required this.id,
    required this.status,
    this.adminNote,
    this.contributorStatus,
  });

  final String id;
  final String status;
  final String? adminNote;
  final String? contributorStatus;

  factory ContributorApplication.fromJson(Map<String, dynamic> json) {
    return ContributorApplication(
      id: '${json['id'] ?? ''}',
      status: '${json['status'] ?? ''}',
      adminNote: json['admin_note'] as String?,
      contributorStatus: json['contributor_status'] as String?,
    );
  }
}

class IssueTake {
  IssueTake({
    required this.id,
    required this.issueId,
    required this.authorId,
    required this.title,
    required this.body,
    required this.status,
    this.displayName,
    this.sourceUrls = const [],
    this.viewCount = 0,
    this.reactionCount = 0,
    this.publishedAt,
    this.createdAt,
    this.adminNote,
  });

  final String id;
  final String issueId;
  final String authorId;
  final String title;
  final String body;
  final String status;
  final String? displayName;
  final List<String> sourceUrls;
  final int viewCount;
  final int reactionCount;
  final String? publishedAt;
  final String? createdAt;
  final String? adminNote;

  factory IssueTake.fromJson(Map<String, dynamic> json) {
    final urls = json['source_urls'];
    return IssueTake(
      id: '${json['id'] ?? ''}',
      issueId: '${json['issue_id'] ?? ''}',
      authorId: '${json['author_id'] ?? ''}',
      title: '${json['title'] ?? ''}',
      body: '${json['body'] ?? ''}',
      status: '${json['status'] ?? ''}',
      displayName: json['display_name'] as String?,
      sourceUrls: urls is List ? urls.map((e) => '$e').toList() : const [],
      viewCount: (json['view_count'] as num?)?.toInt() ?? 0,
      reactionCount: (json['reaction_count'] as num?)?.toInt() ?? 0,
      publishedAt: json['published_at'] as String?,
      createdAt: json['created_at'] as String?,
      adminNote: json['admin_note'] as String?,
    );
  }

  IssueTake copyWith({int? reactionCount}) {
    return IssueTake(
      id: id,
      issueId: issueId,
      authorId: authorId,
      title: title,
      body: body,
      status: status,
      displayName: displayName,
      sourceUrls: sourceUrls,
      viewCount: viewCount,
      reactionCount: reactionCount ?? this.reactionCount,
      publishedAt: publishedAt,
      createdAt: createdAt,
      adminNote: adminNote,
    );
  }
}

class ContributorApi {
  ContributorApi(this._api);

  final ApiClient _api;

  Map<String, String> _uq(String? userId) =>
      (userId == null || userId.isEmpty) ? const {} : {'user_id': userId};

  Future<ContributorMe> fetchMe({String? userId}) async {
    final data = await _api.getJson(
      '/api/v1/contributor/me',
      query: _uq(userId),
    );
    return ContributorMe.fromJson(data);
  }

  Future<ContributorApplication> submitApplication({
    required String motivation,
    required String interests,
    String? userId,
  }) async {
    final data = await _api.postJson(
      '/api/v1/contributor/applications',
      {
        'motivation': motivation,
        'interests': interests,
        'sample_text': '',
        if (userId != null) 'user_id': userId,
      },
      query: _uq(userId),
    );
    return ContributorApplication.fromJson(data);
  }

  Future<List<IssueTake>> fetchIssueTakes(
    String issueId, {
    int limit = 20,
    String? userId,
  }) async {
    final data = await _api.getJson(
      '/api/v1/issues/${Uri.encodeComponent(issueId)}/takes',
      query: {
        'limit': '$limit',
        if (userId != null && userId.isNotEmpty) 'user_id': userId,
      },
    );
    final raw = data['items'];
    if (raw is! List) return const [];
    return raw
        .whereType<Map>()
        .map((e) => IssueTake.fromJson(Map<String, dynamic>.from(e)))
        .toList();
  }

  Future<IssueTake> fetchIssueTake(
    String issueId,
    String takeId, {
    String? userId,
  }) async {
    final data = await _api.getJson(
      '/api/v1/issues/${Uri.encodeComponent(issueId)}/takes/${Uri.encodeComponent(takeId)}',
      query: _uq(userId),
    );
    return IssueTake.fromJson(data);
  }

  Future<List<IssueTake>> fetchMyIssueTakes(
    String issueId, {
    String? userId,
  }) async {
    final raw = await _api.getJsonRaw(
      '/api/v1/issues/${Uri.encodeComponent(issueId)}/takes/mine',
      query: _uq(userId),
    );
    if (raw is List) {
      return raw
          .whereType<Map>()
          .map((e) => IssueTake.fromJson(Map<String, dynamic>.from(e)))
          .toList();
    }
    if (raw is Map && raw['items'] is List) {
      return (raw['items'] as List)
          .whereType<Map>()
          .map((e) => IssueTake.fromJson(Map<String, dynamic>.from(e)))
          .toList();
    }
    return const [];
  }

  Future<IssueTake> createTake({
    required String issueId,
    required String title,
    required String body,
    List<String> sourceUrls = const [],
    String? userId,
  }) async {
    final data = await _api.postJson(
      '/api/v1/issues/${Uri.encodeComponent(issueId)}/takes',
      {
        'title': title,
        'body': body,
        'source_urls': sourceUrls,
        if (userId != null) 'user_id': userId,
      },
      query: _uq(userId),
    );
    return IssueTake.fromJson(data);
  }

  Future<IssueTake> updateTake({
    required String issueId,
    required String takeId,
    String? title,
    String? body,
    List<String>? sourceUrls,
    String? userId,
  }) async {
    final data = await _api.patchJson(
      '/api/v1/issues/${Uri.encodeComponent(issueId)}/takes/${Uri.encodeComponent(takeId)}',
      {
        if (title != null) 'title': title,
        if (body != null) 'body': body,
        if (sourceUrls != null) 'source_urls': sourceUrls,
        if (userId != null) 'user_id': userId,
      },
      query: _uq(userId),
    );
    return IssueTake.fromJson(data);
  }

  Future<IssueTake> submitTake({
    required String issueId,
    required String takeId,
    String? userId,
  }) async {
    final data = await _api.postJson(
      '/api/v1/issues/${Uri.encodeComponent(issueId)}/takes/${Uri.encodeComponent(takeId)}/submit',
      {},
      query: _uq(userId),
    );
    return IssueTake.fromJson(data);
  }

  Future<IssueTake> withdrawTake({
    required String issueId,
    required String takeId,
    String? userId,
  }) async {
    final data = await _api.postJson(
      '/api/v1/issues/${Uri.encodeComponent(issueId)}/takes/${Uri.encodeComponent(takeId)}/withdraw',
      {},
      query: _uq(userId),
    );
    return IssueTake.fromJson(data);
  }

  Future<({int reactionCount, bool alreadyReacted})> reactToTake({
    required String issueId,
    required String takeId,
    String? userId,
  }) async {
    final data = await _api.postJson(
      '/api/v1/issues/${Uri.encodeComponent(issueId)}/takes/${Uri.encodeComponent(takeId)}/reaction',
      {
        if (userId != null) 'user_id': userId,
      },
      query: _uq(userId),
    );
    return (
      reactionCount: (data['reaction_count'] as num?)?.toInt() ?? 0,
      alreadyReacted: data['already_reacted'] == true,
    );
  }
}
