import 'package:flutter_test/flutter_test.dart';
import 'package:takeley/navigation/deep_link.dart';

void main() {
  group('parseDeepLink', () {
    test('parses takeley://i/{id} with sid and ref', () {
      final target = parseDeepLink('takeley://i/abc-123?sid=s1&ref=u9');
      expect(target, isA<SignalLink>());
      final link = target as SignalLink;
      expect(link.signalId, 'abc-123');
      expect(link.shareId, 's1');
      expect(link.refUserId, 'u9');
    });

    test('parses https /i/{id} path', () {
      final target = parseDeepLink('https://api.example/i/issue-9?sid=share');
      expect(target, isA<SignalLink>());
      final link = target as SignalLink;
      expect(link.signalId, 'issue-9');
      expect(link.shareId, 'share');
    });

    test('parses hash SPA route', () {
      final target = parseDeepLink('#/issues/xyz?sid=a&ref=b');
      expect(target, isA<SignalLink>());
      final link = target as SignalLink;
      expect(link.signalId, 'xyz');
      expect(link.shareId, 'a');
      expect(link.refUserId, 'b');
    });

    test('parses push map with issue_id', () {
      final target = parsePushData({
        'issue_id': 'from-push',
        'sid': 's2',
        'nid': 'n1',
      });
      expect(target, isA<SignalLink>());
      final link = target as SignalLink;
      expect(link.signalId, 'from-push');
      expect(link.shareId, 's2');
      expect(link.notificationId, 'n1');
    });

    test('parses settings and home', () {
      expect(parseDeepLink('/settings'), isA<SettingsLink>());
      expect(parseDeepLink('/home'), isA<HomeLink>());
    });

    test('maps takeley:// share button onto /issues/:id', () {
      final loc = routerLocationForUri(
        Uri.parse(
          'takeley://i/4f34cc27-e54c-417e-86aa-f5e5f8e474d3'
          '?sid=s1&ref=u9',
        ),
      );
      expect(loc, '/issues/4f34cc27-e54c-417e-86aa-f5e5f8e474d3?sid=s1&ref=u9');
    });

    test('leaves in-app issue routes alone', () {
      expect(
        routerLocationForUri(Uri.parse('/issues/abc-123?sid=s1')),
        isNull,
      );
    });
  });
}
