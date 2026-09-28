import 'package:flutter_test/flutter_test.dart';
import 'package:takeley/utils/format_news_time.dart';

void main() {
  test('home cards keep first publish even after a content update', () {
    const published = '2026-09-28T08:00:00Z';
    const updated = '2026-09-28T12:00:00Z';
    expect(
      issuePublishedTimestamp(
        publishedAt: published,
        firstSeenAt: '2026-09-28T07:00:00Z',
      ),
      published,
    );
    expect(
      issueStoryTimestamp(
        publishedAt: published,
        contentUpdatedAt: updated,
      ),
      updated,
    );
  });
}
