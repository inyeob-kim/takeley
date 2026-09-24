import 'package:uuid/uuid.dart';

import '../config.dart';

enum ShareIntent { issueOnly, withTake, trend, info }

class SharePayload {
  SharePayload({
    required this.intent,
    required this.title,
    required this.text,
    required this.url,
    required this.shareId,
    required this.shareAsUri,
  });

  final ShareIntent intent;
  final String title;
  final String text;
  final String url;
  final String shareId;

  /// Kakao/iOS: share the landing URL only so OG is one card, not hook + raw link.
  final bool shareAsUri;
}

ShareIntent resolveShareIntent({
  required bool participationSuitable,
  String? trendStatus,
  bool isTrending = false,
}) {
  if (participationSuitable) return ShareIntent.issueOnly;
  final status = (trendStatus ?? '').toUpperCase();
  if (status == 'TRENDING' || status == 'RISING' || isTrending) {
    return ShareIntent.trend;
  }
  return ShareIntent.info;
}

String _truncateTitle(String title, [int max = 48]) {
  final t = title.trim().replaceAll(RegExp(r'\s+'), ' ');
  if (t.length <= max) return t;
  return '${t.substring(0, max - 1).trim()}…';
}

SharePayload buildSharePayload({
  required String id,
  required String title,
  required bool participationSuitable,
  String? trendStatus,
  bool isTrending = false,
  String? shareId,
  String? refUserId,
  bool includeTake = false,
  String? takeLabel,
}) {
  var intent = resolveShareIntent(
    participationSuitable: participationSuitable,
    trendStatus: trendStatus,
    isTrending: isTrending,
  );
  final label = (takeLabel ?? '').trim();
  if (includeTake && label.isNotEmpty && participationSuitable) {
    intent = ShareIntent.withTake;
  }
  final sid = shareId ?? const Uuid().v4();
  final base = kShareOrigin.replaceAll(RegExp(r'/$'), '');
  // Query-less URL so Kakao shows one OG card, not sid/ref/take text.
  final uri = Uri.parse('$base/i/${Uri.encodeComponent(id)}');
  final short = _truncateTitle(title);
  final href = uri.toString();
  final String text;
  switch (intent) {
    case ShareIntent.issueOnly:
      text = '이 이슈, 너는 어떻게 생각해?';
    case ShareIntent.withTake:
      text = '나는 ‘$label’에 한 표 했어. 너는 어떻게 생각해?';
    case ShareIntent.trend:
      text = '이거 지금 관심을 많이 받고 있어.';
    case ShareIntent.info:
      text = '이거 한번 봐봐.';
  }
  return SharePayload(
    intent: intent,
    title: 'TAKELEY · $short',
    text: text,
    url: href,
    shareId: sid,
    shareAsUri: true,
  );
}

String shareIntentName(ShareIntent intent) {
  switch (intent) {
    case ShareIntent.issueOnly:
      return 'issue_only';
    case ShareIntent.withTake:
      return 'with_take';
    case ShareIntent.trend:
      return 'trend';
    case ShareIntent.info:
      return 'info';
  }
}
