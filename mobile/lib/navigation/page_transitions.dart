import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

/// Matches React `ios-slide-from-right` / `signal-detail-enter`
/// (cubic-bezier(0.32, 0.72, 0, 1), ~380ms).
CustomTransitionPage<T> takeleySlidePage<T>({
  required LocalKey key,
  required Widget child,
  Duration duration = const Duration(milliseconds: 380),
}) {
  const curve = Cubic(0.32, 0.72, 0, 1);
  return CustomTransitionPage<T>(
    key: key,
    child: child,
    transitionDuration: duration,
    reverseTransitionDuration: duration,
    transitionsBuilder: (context, animation, secondaryAnimation, child) {
      final curved = CurvedAnimation(parent: animation, curve: curve);
      return FadeTransition(
        opacity: curved,
        child: SlideTransition(
          position: Tween<Offset>(
            begin: const Offset(0.06, 0),
            end: Offset.zero,
          ).animate(curved),
          child: child,
        ),
      );
    },
  );
}

/// Soft fade for sheet-like surfaces (settings).
CustomTransitionPage<T> takeleySheetPage<T>({
  required LocalKey key,
  required Widget child,
  Duration duration = const Duration(milliseconds: 420),
}) {
  const curve = Cubic(0.32, 0.72, 0, 1);
  return CustomTransitionPage<T>(
    key: key,
    child: child,
    transitionDuration: duration,
    reverseTransitionDuration: duration,
    transitionsBuilder: (context, animation, secondaryAnimation, child) {
      final curved = CurvedAnimation(parent: animation, curve: curve);
      return FadeTransition(
        opacity: curved,
        child: SlideTransition(
          position: Tween<Offset>(
            begin: const Offset(0, 0.04),
            end: Offset.zero,
          ).animate(curved),
          child: child,
        ),
      );
    },
  );
}
