import 'api_client.dart';
import 'models.dart';

class ColumnistsApi {
  ColumnistsApi(this._api);

  final ApiClient _api;

  Future<ColumnistProfile> fetchProfile(String id) async {
    final data = await _api.getJson(
      '/api/v1/columnists/${Uri.encodeComponent(id)}',
    );
    return ColumnistProfile.fromJson(data);
  }

  Future<({List<ColumnistIssueCard> items, int count})> fetchIssues(
    String id, {
    required int offset,
    int limit = 10,
  }) async {
    final data = await _api.getJson(
      '/api/v1/columnists/${Uri.encodeComponent(id)}/issues',
      query: {
        'limit': '$limit',
        'offset': '$offset',
      },
    );
    final raw = data['items'];
    final items = raw is List
        ? raw
            .whereType<Map>()
            .map(
              (e) => ColumnistIssueCard.fromJson(
                Map<String, dynamic>.from(e),
              ),
            )
            .toList()
        : <ColumnistIssueCard>[];
    final count = (data['count'] as num?)?.toInt() ?? items.length;
    return (items: items, count: count);
  }
}
