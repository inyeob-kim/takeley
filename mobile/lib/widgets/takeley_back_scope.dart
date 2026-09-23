import 'package:flutter/material.dart';

/// Handles Android system back + iOS edge-swipe when the screen is not a real route.
///
/// [PopScope] alone is not enough on iOS: `canPop: false` disables the Cupertino
/// pop gesture entirely and does not call [onPopInvokedWithResult].
class TakeleyBackScope extends StatelessWidget {
  const TakeleyBackScope({
    super.key,
    required this.onBack,
    required this.child,
  });

  final VoidCallback onBack;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) onBack();
      },
      child: _EdgeBackSwipe(
        onBack: onBack,
        child: child,
      ),
    );
  }
}

class _EdgeBackSwipe extends StatefulWidget {
  const _EdgeBackSwipe({
    required this.onBack,
    required this.child,
  });

  final VoidCallback onBack;
  final Widget child;

  @override
  State<_EdgeBackSwipe> createState() => _EdgeBackSwipeState();
}

class _EdgeBackSwipeState extends State<_EdgeBackSwipe> {
  /// iOS back-gesture zone is roughly this wide.
  static const double _edgeWidth = 36;
  static const double _minDistance = 64;

  double _dragDx = 0;
  bool _tracking = false;

  @override
  Widget build(BuildContext context) {
    // Translucent + drag-only: taps still reach the back button underneath.
    return Stack(
      fit: StackFit.expand,
      children: [
        widget.child,
        Positioned(
          left: 0,
          top: 0,
          bottom: 0,
          width: _edgeWidth,
          child: GestureDetector(
            behavior: HitTestBehavior.translucent,
            onHorizontalDragStart: (_) {
              _tracking = true;
              _dragDx = 0;
            },
            onHorizontalDragUpdate: (details) {
              if (!_tracking) return;
              _dragDx += details.delta.dx;
            },
            onHorizontalDragEnd: (details) {
              if (!_tracking) return;
              final velocity = details.primaryVelocity ?? 0;
              if (_dragDx > _minDistance || velocity > 500) {
                widget.onBack();
              }
              _tracking = false;
              _dragDx = 0;
            },
            onHorizontalDragCancel: () {
              _tracking = false;
              _dragDx = 0;
            },
          ),
        ),
      ],
    );
  }
}
