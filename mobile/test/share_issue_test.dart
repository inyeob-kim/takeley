import 'dart:io';

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
    expect(payload.text, '이 이슈, 너는 어떻게 생각해? 고르면 결과가 열려요.');
    expect(payload.text.contains('http'), isFalse);
    expect(payload.text.contains(payload.url), isFalse);
    expect(payload.url, contains('/i/issue-1'));
    expect(payload.url.contains('sid='), isFalse);
    expect(payload.url.contains('?'), isFalse);
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
    expect(payload.text.contains(payload.url), isFalse);
    expect(payload.url.contains('take='), isFalse);
    expect(payload.url.contains('?'), isFalse);
  });

  test('_sendShare does not pass text and uri together', () {
    final src = File('lib/screens/issue_detail_screen.dart').readAsStringSync();
    expect(src.contains(r"${payload.text}\n${payload.url}"), isFalse);
    expect(src.contains("MethodChannel('takeley/share')"), isTrue);
    expect(src.contains("'text': payload.text"), isTrue);
    expect(src.contains("'url': payload.url"), isTrue);
    expect(src.contains('uri: Uri.parse(payload.url)'), isFalse);
  });
}
