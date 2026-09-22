import '../api/contributor_api.dart';

String takeStatusLabel(String status) {
  switch (status) {
    case 'draft':
      return '작성 중';
    case 'pending_review':
      return '검토 중';
    case 'published':
      return '게시됨';
    case 'rejected':
      return '수정 필요';
    default:
      return status;
  }
}

bool showDeepThoughtWriterCta(String? status) => status == 'APPROVED';

String contributorSettingsLabel(String? status) {
  switch (status) {
    case 'PENDING':
      return '심사 중';
    case 'APPROVED':
      return '활동 중';
    case 'REJECTED':
      return '신청 결과';
    case 'SUSPENDED':
      return '이용 제한';
    default:
      return '신청하기';
  }
}

String deepFocusForMyTake(String status) =>
    status == 'published' ? 'detail' : 'writer';

bool isTakeEditingLocked(String status) =>
    status == 'pending_review' || status == 'published';

List<String> parseSourceUrls(String raw) {
  return raw
      .split(RegExp(r'[\n,]+'))
      .map((s) => s.trim())
      .where((s) => s.isNotEmpty)
      .toList();
}

bool looksLikeHttpUrl(String url) {
  final u = Uri.tryParse(url);
  if (u == null) return false;
  return u.scheme == 'http' || u.scheme == 'https';
}

({bool ok, String? message, List<String> sourceUrls}) validateDeepThoughtFields(
  String title,
  String body,
  String sourcesRaw,
) {
  if (title.trim().isEmpty) {
    return (ok: false, message: '제목을 입력해 주세요.', sourceUrls: const []);
  }
  if (body.trim().isEmpty) {
    return (ok: false, message: '생각을 입력해 주세요.', sourceUrls: const []);
  }
  final sourceUrls = parseSourceUrls(sourcesRaw);
  for (final u in sourceUrls) {
    if (!looksLikeHttpUrl(u)) {
      return (
        ok: false,
        message: '출처는 http(s) URL만 넣을 수 있어요.',
        sourceUrls: const [],
      );
    }
  }
  return (ok: true, message: null, sourceUrls: sourceUrls);
}

bool isDeepThoughtDirty(
  String title,
  String body,
  String sourcesRaw,
  ({String title, String body, List<String> sourceUrls})? saved,
) {
  final t = title.trim();
  final b = body.trim();
  final sources = parseSourceUrls(sourcesRaw).join('\n');
  if (saved == null) return t.isNotEmpty || b.isNotEmpty || sources.isNotEmpty;
  final savedSources = saved.sourceUrls
      .map((s) => s.trim())
      .where((s) => s.isNotEmpty)
      .join('\n');
  return t != saved.title.trim() ||
      b != saved.body.trim() ||
      sources != savedSources;
}

bool canSaveDeepThought(
  String title,
  String body,
  String sourcesRaw,
  ({String title, String body, List<String> sourceUrls})? saved,
) {
  if (title.trim().isEmpty || body.trim().isEmpty) return false;
  return isDeepThoughtDirty(title, body, sourcesRaw, saved);
}

const _contributorApiErrorKo = <String, String>{
  'Contributor permission required':
      '깊이 있는 생각을 남기려면 설정에서 먼저 신청해 주세요.',
  'Contributor suspended': '지금은 글 쓰는 기능을 이용할 수 없어요.',
  'Already an approved contributor': '이미 글 쓰는 분으로 활동 중이에요.',
  'Application already pending': '이미 심사 중인 신청이 있어요.',
  'Cannot apply in current status': '지금은 신청할 수 없어요.',
  'User not found': '사용자를 찾을 수 없어요.',
  'User inactive': '이용이 제한된 계정이에요.',
  'Issue not found': '이슈를 찾을 수 없어요.',
  'IssueTake not found': '생각을 찾을 수 없어요.',
  'Not the author': '작성자만 할 수 있어요.',
  'Cannot edit while pending review': '검토 중에는 수정할 수 없어요.',
  'Cannot edit published take': '게시된 생각은 수정할 수 없어요.',
  'Only draft can be submitted': '작성 중인 생각만 검토 요청할 수 있어요.',
  'Only pending_review can be withdrawn': '검토 중인 생각만 취소할 수 있어요.',
  'title and body required': '제목과 본문을 입력해 주세요.',
  'Only published takes accept reactions': '게시된 생각에만 공감할 수 있어요.',
};

String formatContributorApiError(String? message, [String fallback = '요청을 처리하지 못했어요']) {
  final raw = (message ?? '').trim();
  if (raw.isEmpty) return fallback;
  return _contributorApiErrorKo[raw] ?? raw;
}

String previewBody(String body, [int max = 120]) {
  final text = body.replaceAll(RegExp(r'\s+'), ' ').trim();
  if (text.length <= max) return text;
  return '${text.substring(0, max).trim()}…';
}

/// Issue detail preview: how many deep thoughts to show before “더 보기”.
const int kDeepThoughtPreviewLimit = 3;

DateTime? _takeTimestamp(IssueTake take) {
  final raw = (take.publishedAt ?? take.createdAt ?? '').trim();
  if (raw.isEmpty) return null;
  return DateTime.tryParse(raw);
}

/// Rank: 공감 → 조회 → 최신.
List<IssueTake> rankIssueTakes(List<IssueTake> takes) {
  final ranked = List<IssueTake>.from(takes);
  ranked.sort((a, b) {
    final byReaction = b.reactionCount.compareTo(a.reactionCount);
    if (byReaction != 0) return byReaction;
    final byView = b.viewCount.compareTo(a.viewCount);
    if (byView != 0) return byView;
    final ta = _takeTimestamp(a) ?? DateTime.fromMillisecondsSinceEpoch(0);
    final tb = _takeTimestamp(b) ?? DateTime.fromMillisecondsSinceEpoch(0);
    return tb.compareTo(ta);
  });
  return ranked;
}

