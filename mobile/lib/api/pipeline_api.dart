import 'api_client.dart';

class PipelineStatus {
  PipelineStatus({
    required this.collecting,
    required this.unprocessedRaw,
    required this.publishedIssues,
    required this.message,
    this.draftIssues = 0,
  });

  final bool collecting;
  final int unprocessedRaw;
  final int publishedIssues;
  final int draftIssues;
  final String message;

  factory PipelineStatus.fromJson(Map<String, dynamic> json) {
    return PipelineStatus(
      collecting: json['collecting'] == true,
      unprocessedRaw: (json['unprocessed_raw'] as num?)?.toInt() ?? 0,
      publishedIssues: (json['published_issues'] as num?)?.toInt() ?? 0,
      draftIssues: (json['draft_issues'] as num?)?.toInt() ?? 0,
      message: '${json['message'] ?? ''}',
    );
  }
}

class PipelineApi {
  PipelineApi(this._api);

  final ApiClient _api;

  Future<PipelineStatus> fetchStatus() async {
    final data = await _api.getJson('/api/v1/pipeline/status');
    return PipelineStatus.fromJson(data);
  }
}
