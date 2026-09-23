import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../theme/takeley_colors.dart';

/// Circular columnist photo. Same crop on profile and byline — uniform
/// scale only, face anchored to the top so the crown is not clipped.
class ColumnistAvatar extends StatelessWidget {
  const ColumnistAvatar({
    super.key,
    required this.size,
    this.imageUrl,
    this.initial = '?',
  });

  final double size;
  final String? imageUrl;
  final String initial;

  @override
  Widget build(BuildContext context) {
    return ClipOval(
      child: SizedBox(
        width: size,
        height: size,
        child: imageUrl != null
            ? CachedNetworkImage(
                imageUrl: imageUrl!,
                fit: BoxFit.cover,
                alignment: Alignment.topCenter,
                fadeInDuration: Duration.zero,
                errorWidget: (_, __, ___) => _fallback(),
              )
            : _fallback(),
      ),
    );
  }

  Widget _fallback() {
    return ColoredBox(
      color: TakeleyColors.accentSoft,
      child: Center(
        child: Text(
          initial,
          style: TextStyle(
            color: TakeleyColors.accent,
            fontWeight: FontWeight.w700,
            fontSize: size * 0.38,
          ),
        ),
      ),
    );
  }
}
