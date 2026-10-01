String categoryLabel(String? raw) {
  final value = (raw ?? 'TAKE').trim();
  if (value.isEmpty) return 'TAKE';
  if (RegExp(r'^[a-zA-Z0-9\s/_-]+$').hasMatch(value)) {
    return value.toUpperCase();
  }
  return value;
}
