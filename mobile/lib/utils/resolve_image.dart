import '../config.dart';

String? resolveImageUrl(String? url) {
  if (url == null) return null;
  final text = url.trim();
  if (text.isEmpty) return null;
  if (RegExp(r'^https?:\/\/', caseSensitive: false).hasMatch(text)) {
    return text;
  }
  final base = kApiBaseUrl.endsWith('/')
      ? kApiBaseUrl.substring(0, kApiBaseUrl.length - 1)
      : kApiBaseUrl;
  return '$base${text.startsWith('/') ? '' : '/'}$text';
}
