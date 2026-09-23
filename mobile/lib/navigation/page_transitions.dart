import 'package:flutter/cupertino.dart';

/// Pushed routes use [CupertinoPage] so iOS edge-swipe pop works.
/// (CustomTransitionPage disables the interactive back gesture.)
CupertinoPage<T> takeleySlidePage<T>({
  required LocalKey key,
  required Widget child,
}) {
  return CupertinoPage<T>(
    key: key,
    child: child,
  );
}

/// Settings / sheet-style push — same gesture support as [takeleySlidePage].
CupertinoPage<T> takeleySheetPage<T>({
  required LocalKey key,
  required Widget child,
}) {
  return CupertinoPage<T>(
    key: key,
    child: child,
  );
}
