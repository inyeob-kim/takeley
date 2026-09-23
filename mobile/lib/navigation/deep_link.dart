/// Deep-link targets from FCM data, custom scheme, or share URLs.
sealed class DeepLinkTarget {
  const DeepLinkTarget();
}

class HomeLink extends DeepLinkTarget {
  const HomeLink();
}

class BriefLink extends DeepLinkTarget {
  const BriefLink();
}

class SettingsLink extends DeepLinkTarget {
  const SettingsLink();
}

class SignalLink extends DeepLinkTarget {
  const SignalLink(
    this.signalId, {
    this.notificationId,
    this.shareId,
    this.refUserId,
  });

  final String signalId;
  final String? notificationId;
  final String? shareId;
  final String? refUserId;
}

DeepLinkTarget? parsePushData(Map<String, dynamic> data) {
  return parseDeepLink({
    for (final e in data.entries) e.key: '${e.value ?? ''}',
  });
}

DeepLinkTarget? parseDeepLink(Object? input) {
  if (input == null) return null;

  var route = '';
  var signalId = '';
  var issueId = '';
  var shareId = '';
  var refUserId = '';
  var notificationId = '';

  if (input is String) {
    final raw = input.trim();
    if (raw.isEmpty) return null;
    try {
      if (raw.startsWith('http://') ||
          raw.startsWith('https://') ||
          raw.startsWith('takeley:')) {
        final normalized =
            raw.startsWith('takeley:') && !raw.startsWith('takeley://')
                ? raw.replaceFirst('takeley:', 'takeley://')
                : raw;
        final u = Uri.parse(normalized);
        // takeley://i/{id} → host=i, path=/{id}; combine only for custom schemes.
        final path = (u.scheme == 'takeley' && u.host.isNotEmpty)
            ? '/${u.host}${u.path}'
            : u.path;
        signalId = u.queryParameters['signal_id'] ?? '';
        issueId = u.queryParameters['issue_id'] ?? '';
        shareId = u.queryParameters['sid'] ??
            u.queryParameters['share_id'] ??
            '';
        refUserId = u.queryParameters['ref'] ?? '';
        notificationId = _readNid(u.queryParameters);
        route = u.queryParameters['route'] ?? path;
        final frag = u.fragment;
        if (frag.isNotEmpty) {
          final hashPath = frag.startsWith('/') ? frag : '/$frag';
          final qIdx = hashPath.indexOf('?');
          final pathOnly = qIdx >= 0 ? hashPath.substring(0, qIdx) : hashPath;
          if (qIdx >= 0) {
            final hp = Uri.splitQueryString(hashPath.substring(qIdx + 1));
            if (shareId.isEmpty) {
              shareId = hp['sid'] ?? hp['share_id'] ?? '';
            }
            if (refUserId.isEmpty) refUserId = hp['ref'] ?? '';
            if (notificationId.isEmpty) notificationId = _readNid(hp);
          }
          if ((u.queryParameters['route'] ?? '').isEmpty) {
            route = pathOnly;
          }
        }
      } else {
        var path = raw.replaceFirst(RegExp(r'^#'), '');
        final qIdx = path.indexOf('?');
        if (qIdx >= 0) {
          final params = Uri.splitQueryString(path.substring(qIdx + 1));
          shareId = params['sid'] ?? params['share_id'] ?? '';
          refUserId = params['ref'] ?? '';
          notificationId = _readNid(params);
          path = path.substring(0, qIdx);
        }
        route = path;
      }
    } catch (_) {
      route = raw.replaceFirst(RegExp(r'^#'), '');
    }
  } else if (input is Map) {
    final map = <String, String>{
      for (final e in input.entries) '${e.key}': '${e.value ?? ''}',
    };
    route = map['route'] ?? '';
    signalId = map['signal_id'] ?? '';
    issueId = map['issue_id'] ?? '';
    shareId = map['sid'] ?? map['share_id'] ?? '';
    refUserId = map['ref'] ?? '';
    notificationId = _readNid(map);
  } else {
    return null;
  }

  if (issueId.isNotEmpty) {
    return _issueLink(issueId, shareId, refUserId, notificationId);
  }
  if (signalId.isNotEmpty) {
    return _issueLink(signalId, shareId, refUserId, notificationId);
  }

  final matched = _matchIssue(route);
  if (matched != null) {
    return _issueLink(matched, shareId, refUserId, notificationId);
  }

  final lower = route.toLowerCase();
  if (lower.contains('settings')) return const SettingsLink();
  if (lower.contains('brief')) return const BriefLink();
  if (lower.contains('home') || route == '/' || route.isEmpty) {
    return const HomeLink();
  }
  return null;
}

String? _matchIssue(String route) {
  final patterns = <RegExp>[
    RegExp(r'/issues/([^/?#]+)', caseSensitive: false),
    RegExp(r'^issues/([^/?#]+)', caseSensitive: false),
    RegExp(r'/i/([^/?#]+)', caseSensitive: false),
    RegExp(r'^i/([^/?#]+)', caseSensitive: false),
    RegExp(r'/signals/([^/?#]+)', caseSensitive: false),
    RegExp(r'^signals/([^/?#]+)', caseSensitive: false),
  ];
  for (final re in patterns) {
    final m = re.firstMatch(route);
    if (m != null) {
      final id = Uri.decodeComponent(m.group(1)!);
      if (id.isNotEmpty) return id;
    }
  }
  return null;
}

SignalLink _issueLink(
  String id,
  String shareId,
  String refUserId,
  String notificationId,
) {
  return SignalLink(
    id,
    shareId: shareId.isNotEmpty ? shareId : null,
    refUserId: refUserId.isNotEmpty ? refUserId : null,
    notificationId: notificationId.isNotEmpty ? notificationId : null,
  );
}

String _readNid(Map<String, String> params) {
  final nid = params['nid'] ?? params['notification_id'] ?? '';
  return nid;
}

String issueRoutePath(SignalLink link) {
  final q = <String, String>{
    if (link.shareId != null && link.shareId!.isNotEmpty) 'sid': link.shareId!,
    if (link.refUserId != null && link.refUserId!.isNotEmpty)
      'ref': link.refUserId!,
  };
  if (q.isEmpty) return '/issues/${link.signalId}';
  return Uri(path: '/issues/${link.signalId}', queryParameters: q).toString();
}

/// Maps a platform / share URI onto an in-app GoRouter location.
String? routerLocationForUri(Uri uri) {
  final path = uri.path;
  if (path == '/home' ||
      path == '/activity' ||
      path == '/profile' ||
      path == '/settings' ||
      path.startsWith('/issues/')) {
    return null;
  }
  final target = parseDeepLink(uri.toString());
  if (target is SignalLink) return issueRoutePath(target);
  if (target is SettingsLink) return '/settings';
  if (target is BriefLink || target is HomeLink) return '/home';
  if (uri.scheme == 'takeley' || path.isEmpty || path == '/') {
    return '/home';
  }
  return null;
}
