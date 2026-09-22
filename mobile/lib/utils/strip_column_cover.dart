/// Column detail shows published `column_body` as-is.
/// Kept as a no-op for any leftover call sites.
String prepareColumnBodyForDisplay(
  String body, {
  String? coverUrl,
  String? summary,
  String? title,
}) {
  return body;
}

/// @deprecated Use [prepareColumnBodyForDisplay].
String stripLeadingCoverFromColumnBody(String body, String? coverUrl) {
  return body;
}
