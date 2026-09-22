String categoryLabel(String? raw) {
  final value = (raw ?? '이슈').trim();
  if (value.isEmpty) return '이슈';
  if (RegExp(r'^[a-zA-Z0-9\s/_-]+$').hasMatch(value)) {
    return value.toUpperCase();
  }
  return value;
}
