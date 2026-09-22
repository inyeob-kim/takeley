import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../theme/takeley_colors.dart';

/// Centers content at ~430px on wide web viewports (design-system layout).
/// Keeps an explicit height so nested scrollables do not collapse to zero.
class PhoneFrame extends StatelessWidget {
  const PhoneFrame({super.key, required this.child});

  static const double maxContentWidth = 430;

  final Widget child;

  @override
  Widget build(BuildContext context) {
    if (!kIsWeb) return child;

    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth > maxContentWidth;
        if (!wide) return child;

        return ColoredBox(
          color: TakeleyColors.frameOutside,
          child: Center(
            child: SizedBox(
              width: maxContentWidth,
              height: constraints.maxHeight,
              child: ColoredBox(
                color: TakeleyColors.canvas,
                child: child,
              ),
            ),
          ),
        );
      },
    );
  }
}
