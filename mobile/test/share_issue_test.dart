import 'package:flutter_test/flutter_test.dart';
import 'package:takeley/utils/share_issue.dart';

void main() {
  test('issue-only share is a landing URI, not hook + raw URL text', () {
    final payload = buildSharePayload(
      id: 'issue-1',
      title: 'AI가 일자리를 바꾸면 우리는 무엇을 해야 할까?',
      participationSuitable: true,
      shareId: 'sid-1',
    );
    expect(payload.intent, ShareIntent.issueOnly);
    expect(payload.shareAsUri, isTrue);
    expect(payload.text.contains('http'), isFalse);
    expect(payload.url, contains('/i/issue-1'));
    expect(payload.url.contains('sid='), isFalse);
  });

  test('with-take share is a clean landing URI', () {
    final payload = buildSharePayload(
      id: 'issue-1',
      title: '제목',
      participationSuitable: true,
      includeTake: true,
      takeLabel: '좋아하는 일을 한다',
      shareId: 'sid-2',
    );
    expect(payload.intent, ShareIntent.withTake);
    expect(payload.shareAsUri, isTrue);
    expect(payload.text.contains('http'), isFalse);
    expect(payload.url.contains('take='), isFalse);
    expect(payload.url.contains('?'), isFalse);
  });
}
