DateTime? parseApiDate(String? raw) {
  if (raw == null) return null;
  final s = raw.trim();
  if (s.isEmpty) return null;
  final hasZone = RegExp(r'(?:Z|[+-]\d{2}:?\d{2})$', caseSensitive: false)
      .hasMatch(s);
  final looksIso = RegExp(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}').hasMatch(s);
  final then = DateTime.tryParse(looksIso && !hasZone ? '${s}Z' : s);
  if (then == null) return null;
  return then.toLocal();
}

String formatNewsTime(String? raw, {DateTime? now}) {
  final then = parseApiDate(raw);
  if (then == null) return '';
  final n = now ?? DateTime.now();
  final diffMs = n.difference(then).inMilliseconds;
  if (diffMs < 0) return '방금 전';

  final minutes = diffMs ~/ 60000;
  if (minutes < 1) return '방금 전';
  if (minutes < 60) return '$minutes분 전';

  final todayStart = DateTime(n.year, n.month, n.day);
  final thenStart = DateTime(then.year, then.month, then.day);
  final dayDiff = todayStart.difference(thenStart).inDays;

  if (dayDiff == 0) {
    final hours = (minutes / 60).floor().clamp(1, 24);
    return '$hours시간 전';
  }
  if (dayDiff == 1) return '어제';
  return '${then.month}.${then.day}';
}
