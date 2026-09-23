class IssueOption {
  IssueOption({
    required this.id,
    required this.label,
    required this.displayOrder,
    required this.count,
  });

  final String id;
  final String label;
  final int displayOrder;
  final int count;

  factory IssueOption.fromJson(Map<String, dynamic> json) {
    return IssueOption(
      id: '${json['id'] ?? ''}',
      label: '${json['label'] ?? ''}',
      displayOrder: (json['display_order'] as num?)?.toInt() ?? 0,
      count: (json['count'] as num?)?.toInt() ?? 0,
    );
  }
}

class IssueSource {
  IssueSource({
    required this.id,
    this.url,
    this.provider,
    this.title,
    this.excerpt,
    this.author,
  });

  final String id;
  final String? url;
  final String? provider;
  final String? title;
  final String? excerpt;
  final String? author;

  factory IssueSource.fromJson(Map<String, dynamic> json) {
    return IssueSource(
      id: '${json['id'] ?? ''}',
      url: json['url'] as String?,
      provider: json['provider'] as String?,
      title: json['title'] as String?,
      excerpt: json['excerpt'] as String?,
      author: json['author'] as String?,
    );
  }
}

class Issue {
  Issue({
    required this.id,
    required this.title,
    required this.summary,
    this.whyItMatters = '',
    this.columnBody = '',
    this.columnAuthorName,
    this.columnAuthorImageUrl,
    this.columnistId,
    this.imageUrl,
    this.keyPoints = const [],
    this.category,
    this.topic,
    this.trendScore = 0,
    this.isTrending = false,
    this.trendStatus = 'NORMAL',
    this.importance = 0,
    this.confidence = 0,
    this.contentType = '',
    this.evidenceLevel = '',
    this.relatedSymbols = const [],
    this.participationSuitable = false,
    this.participationType,
    this.participationQuestion,
    this.options = const [],
    this.participationCount = 0,
    this.myOptionId,
    this.sourceCount = 0,
    this.sources = const [],
    this.showSources = false,
    this.commentCount = 0,
    this.impressionCount = 0,
    this.openCount = 0,
    this.status = '',
    this.publishedAt,
    this.firstSeenAt,
    this.updatedAt,
    this.contentUpdatedAt,
    this.isFollowing = false,
    this.hasNewUpdate = false,
    this.myLastSeenAt,
  });

  final String id;
  final String title;
  final String summary;
  final String whyItMatters;
  final String columnBody;
  final String? columnAuthorName;
  final String? columnAuthorImageUrl;
  final String? columnistId;
  final String? imageUrl;
  final List<String> keyPoints;
  final String? category;
  final String? topic;
  final double trendScore;
  final bool isTrending;
  final String trendStatus;
  final double importance;
  final double confidence;
  final String contentType;
  final String evidenceLevel;
  final List<String> relatedSymbols;
  final bool participationSuitable;
  final String? participationType;
  final String? participationQuestion;
  final List<IssueOption> options;
  final int participationCount;
  final String? myOptionId;
  final int sourceCount;
  final List<IssueSource> sources;
  final bool showSources;
  final int commentCount;
  final int impressionCount;
  final int openCount;
  final String status;
  final String? publishedAt;
  final String? firstSeenAt;
  final String? updatedAt;
  final String? contentUpdatedAt;
  final bool isFollowing;
  final bool hasNewUpdate;
  final String? myLastSeenAt;

  factory Issue.fromJson(Map<String, dynamic> json) {
    final optionsRaw = json['options'];
    final sourcesRaw = json['sources'];
    final keyPointsRaw = json['key_points'];
    final symbolsRaw = json['related_symbols'];
    final trend =
        '${json['trend_status'] ?? (json['is_trending'] == true ? 'TRENDING' : 'NORMAL')}'
            .toUpperCase();

    return Issue(
      id: '${json['id'] ?? ''}',
      title: '${json['title'] ?? ''}',
      summary: '${json['summary'] ?? ''}',
      whyItMatters: '${json['why_it_matters'] ?? ''}',
      columnBody: '${json['column_body'] ?? ''}',
      columnAuthorName: json['column_author_name'] as String?,
      columnAuthorImageUrl: json['column_author_image_url'] as String?,
      columnistId: json['columnist_id'] as String?,
      imageUrl: json['image_url'] as String?,
      keyPoints: keyPointsRaw is List
          ? keyPointsRaw.map((e) => '$e').toList()
          : const [],
      category: json['category'] as String?,
      topic: json['topic'] as String?,
      trendScore: (json['trend_score'] as num?)?.toDouble() ?? 0,
      isTrending: json['is_trending'] == true,
      trendStatus: trend,
      importance: (json['importance'] as num?)?.toDouble() ?? 0,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
      contentType: '${json['content_type'] ?? ''}',
      evidenceLevel: '${json['evidence_level'] ?? ''}',
      relatedSymbols: symbolsRaw is List
          ? symbolsRaw.map((e) => '$e').toList()
          : const [],
      participationSuitable: json['participation_suitable'] == true,
      participationType: json['participation_type'] as String?,
      participationQuestion: json['participation_question'] as String?,
      options: optionsRaw is List
          ? optionsRaw
              .whereType<Map>()
              .map((e) => IssueOption.fromJson(Map<String, dynamic>.from(e)))
              .toList()
          : const [],
      participationCount: (json['participation_count'] as num?)?.toInt() ?? 0,
      myOptionId: json['my_option_id'] as String?,
      sourceCount: (json['source_count'] as num?)?.toInt() ?? 0,
      sources: sourcesRaw is List
          ? sourcesRaw
              .whereType<Map>()
              .map((e) => IssueSource.fromJson(Map<String, dynamic>.from(e)))
              .toList()
          : const [],
      showSources: json['show_sources'] == true,
      commentCount: (json['comment_count'] as num?)?.toInt() ?? 0,
      impressionCount: (json['impression_count'] as num?)?.toInt() ?? 0,
      openCount: (json['open_count'] as num?)?.toInt() ?? 0,
      status: '${json['status'] ?? ''}',
      publishedAt: json['published_at'] as String?,
      firstSeenAt: json['first_seen_at'] as String?,
      updatedAt: json['updated_at'] as String?,
      contentUpdatedAt: json['content_updated_at'] as String?,
      isFollowing: json['is_following'] == true,
      hasNewUpdate: json['has_new_update'] == true,
      myLastSeenAt: json['my_last_seen_at'] as String?,
    );
  }

  Issue copyWith({
    String? myOptionId,
    int? participationCount,
    List<IssueOption>? options,
    bool? isFollowing,
    int? commentCount,
  }) {
    return Issue(
      id: id,
      title: title,
      summary: summary,
      whyItMatters: whyItMatters,
      columnBody: columnBody,
      columnAuthorName: columnAuthorName,
      columnAuthorImageUrl: columnAuthorImageUrl,
      columnistId: columnistId,
      imageUrl: imageUrl,
      keyPoints: keyPoints,
      category: category,
      topic: topic,
      trendScore: trendScore,
      isTrending: isTrending,
      trendStatus: trendStatus,
      importance: importance,
      confidence: confidence,
      contentType: contentType,
      evidenceLevel: evidenceLevel,
      relatedSymbols: relatedSymbols,
      participationSuitable: participationSuitable,
      participationType: participationType,
      participationQuestion: participationQuestion,
      options: options ?? this.options,
      participationCount: participationCount ?? this.participationCount,
      myOptionId: myOptionId ?? this.myOptionId,
      sourceCount: sourceCount,
      sources: sources,
      showSources: showSources,
      commentCount: commentCount ?? this.commentCount,
      impressionCount: impressionCount,
      openCount: openCount,
      status: status,
      publishedAt: publishedAt,
      firstSeenAt: firstSeenAt,
      updatedAt: updatedAt,
      contentUpdatedAt: contentUpdatedAt,
      isFollowing: isFollowing ?? this.isFollowing,
      hasNewUpdate: hasNewUpdate,
      myLastSeenAt: myLastSeenAt,
    );
  }
}

class IssueComment {
  IssueComment({
    required this.id,
    required this.issueId,
    required this.userId,
    required this.content,
    required this.likeCount,
    required this.createdAt,
    this.displayName,
    this.issueTitle = '',
  });

  final String id;
  final String issueId;
  final String userId;
  final String content;
  final int likeCount;
  final String createdAt;
  final String? displayName;
  final String issueTitle;

  factory IssueComment.fromJson(Map<String, dynamic> json) {
    return IssueComment(
      id: '${json['id'] ?? ''}',
      issueId: '${json['issue_id'] ?? ''}',
      userId: '${json['user_id'] ?? ''}',
      content: '${json['content'] ?? ''}',
      likeCount: (json['like_count'] as num?)?.toInt() ?? 0,
      createdAt: '${json['created_at'] ?? ''}',
      displayName: json['display_name'] as String?,
      issueTitle: '${json['issue_title'] ?? ''}',
    );
  }
}

class MyActivity {
  MyActivity({
    required this.participations,
    required this.followed,
    required this.comments,
    this.contributorStats,
    this.myDeepThoughts = const [],
  });

  final List<Issue> participations;
  final List<Issue> followed;
  final List<IssueComment> comments;
  final ContributorStats? contributorStats;
  final List<MyDeepThought> myDeepThoughts;

  factory MyActivity.fromJson(Map<String, dynamic> json) {
    List<Issue> issues(dynamic raw) {
      if (raw is! List) return const [];
      return raw
          .whereType<Map>()
          .map((e) => Issue.fromJson(Map<String, dynamic>.from(e)))
          .toList();
    }

    List<IssueComment> comments(dynamic raw) {
      if (raw is! List) return const [];
      return raw
          .whereType<Map>()
          .map((e) => IssueComment.fromJson(Map<String, dynamic>.from(e)))
          .toList();
    }

    List<MyDeepThought> thoughts(dynamic raw) {
      if (raw is! List) return const [];
      return raw
          .whereType<Map>()
          .map((e) => MyDeepThought.fromJson(Map<String, dynamic>.from(e)))
          .toList();
    }

    final stats = json['contributor_stats'];
    return MyActivity(
      participations: issues(json['participations']),
      followed: issues(json['followed']),
      comments: comments(json['comments']),
      contributorStats: stats is Map
          ? ContributorStats.fromJson(Map<String, dynamic>.from(stats))
          : null,
      myDeepThoughts: thoughts(json['my_deep_thoughts']),
    );
  }
}

class ContributorStats {
  ContributorStats({
    required this.takesCount,
    required this.totalViews,
    required this.totalReactions,
  });

  final int takesCount;
  final int totalViews;
  final int totalReactions;

  factory ContributorStats.fromJson(Map<String, dynamic> json) {
    return ContributorStats(
      takesCount: (json['takes_count'] as num?)?.toInt() ?? 0,
      totalViews: (json['total_views'] as num?)?.toInt() ?? 0,
      totalReactions: (json['total_reactions'] as num?)?.toInt() ?? 0,
    );
  }
}

class MyDeepThought {
  MyDeepThought({
    required this.id,
    required this.issueId,
    required this.issueTitle,
    required this.title,
    required this.status,
    this.viewCount = 0,
    this.reactionCount = 0,
    this.createdAt,
    this.updatedAt,
    this.publishedAt,
  });

  final String id;
  final String issueId;
  final String issueTitle;
  final String title;
  final String status;
  final int viewCount;
  final int reactionCount;
  final String? createdAt;
  final String? updatedAt;
  final String? publishedAt;

  factory MyDeepThought.fromJson(Map<String, dynamic> json) {
    return MyDeepThought(
      id: '${json['id'] ?? ''}',
      issueId: '${json['issue_id'] ?? ''}',
      issueTitle: '${json['issue_title'] ?? ''}',
      title: '${json['title'] ?? ''}',
      status: '${json['status'] ?? ''}',
      viewCount: (json['view_count'] as num?)?.toInt() ?? 0,
      reactionCount: (json['reaction_count'] as num?)?.toInt() ?? 0,
      createdAt: json['created_at'] as String?,
      updatedAt: json['updated_at'] as String?,
      publishedAt: json['published_at'] as String?,
    );
  }
}

class UserSettings {
  UserSettings({
    required this.userId,
    required this.notificationsEnabled,
    this.displayName,
    this.briefAlarmTime,
    this.timezone,
    this.ttsVoiceGender,
  });

  final String userId;
  final bool notificationsEnabled;
  final String? displayName;
  final String? briefAlarmTime;
  final String? timezone;
  final String? ttsVoiceGender;

  factory UserSettings.fromJson(Map<String, dynamic> json) {
    final name = (json['display_name'] as String?)?.trim();
    return UserSettings(
      userId: '${json['user_id'] ?? ''}',
      notificationsEnabled: json['notifications_enabled'] != false,
      displayName: (name != null && name.isNotEmpty) ? name : null,
      briefAlarmTime: json['brief_alarm_time'] as String?,
      timezone: json['timezone'] as String?,
      ttsVoiceGender: json['tts_voice_gender'] as String?,
    );
  }
}

class ColumnistIssueCard {
  ColumnistIssueCard({
    required this.id,
    required this.title,
    required this.summary,
    this.category,
    this.imageUrl,
    this.publishedAt,
    this.contentUpdatedAt,
  });

  final String id;
  final String title;
  final String summary;
  final String? category;
  final String? imageUrl;
  final String? publishedAt;
  final String? contentUpdatedAt;

  factory ColumnistIssueCard.fromJson(Map<String, dynamic> json) {
    return ColumnistIssueCard(
      id: '${json['id'] ?? ''}',
      title: '${json['title'] ?? ''}',
      summary: '${json['summary'] ?? ''}',
      category: json['category'] as String?,
      imageUrl: json['image_url'] as String?,
      publishedAt: json['published_at'] as String?,
      contentUpdatedAt: json['content_updated_at'] as String?,
    );
  }
}

class ColumnistProfile {
  ColumnistProfile({
    required this.id,
    required this.displayName,
    this.headline = '',
    this.bio = '',
    this.specialties = const [],
    this.email,
    this.imageUrl,
    this.status = 'active',
    this.issueCount = 0,
    this.issues = const [],
  });

  final String id;
  final String displayName;
  final String headline;
  final String bio;
  final List<String> specialties;
  final String? email;
  final String? imageUrl;
  final String status;
  final int issueCount;
  final List<ColumnistIssueCard> issues;

  factory ColumnistProfile.fromJson(Map<String, dynamic> json) {
    final raw = json['issues'];
    final specs = json['specialties'];
    return ColumnistProfile(
      id: '${json['id'] ?? ''}',
      displayName: '${json['display_name'] ?? ''}',
      headline: '${json['headline'] ?? ''}',
      bio: '${json['bio'] ?? ''}',
      specialties: specs is List
          ? specs
              .map((e) => '$e'.trim())
              .where((e) => e.isNotEmpty)
              .toList()
          : const [],
      email: (json['email'] as String?)?.trim(),
      imageUrl: json['image_url'] as String?,
      status: '${json['status'] ?? 'active'}',
      issueCount: (json['issue_count'] as num?)?.toInt() ??
          (raw is List ? raw.length : 0),
      issues: raw is List
          ? raw
              .whereType<Map>()
              .map(
                (e) => ColumnistIssueCard.fromJson(
                  Map<String, dynamic>.from(e),
                ),
              )
              .toList()
          : const [],
    );
  }
}
