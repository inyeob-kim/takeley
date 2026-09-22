import 'package:flutter/material.dart';

/// Design tokens — `.cursor/rules/design-system.mdc` / React `index.css`.
abstract final class TakeleyColors {
  static const Color accent = Color(0xFF2D5BE3);
  static const Color accentSoft = Color(0xFFE8EEFC);
  static const Color rising = Color(0xFFE85D04);
  static const Color fg = Color(0xFF0A0A0A);
  static const Color muted = Color(0xFF4B5563);
  static const Color canvas = Color(0xFFFFFFFF);
  static const Color soft = Color(0xFFF7F8FA);
  /// iOS-style group fill — React `#f2f2f7` profile/settings pills.
  static const Color pill = Color(0xFFF2F2F7);
  static const Color secondaryLabel = Color(0xFF6E6E73);
  static const Color avatarRing = Color(0xFFE5E5EA);
  static const Color chevron = Color(0xFFC7C7CC);
  static const Color switchOn = Color(0xFF34C759);
  static const Color craft = Color(0xFFA1A1AA);
  static const Color border = Color(0x14000000); // rgba(0,0,0,0.08)
  static const Color hairline = Color(0x1A000000); // rgba(0,0,0,0.10)
  static const Color danger = Color(0xFFDC2626);
  static const Color frameOutside = Color(0xFFEEF0F3);

  static List<BoxShadow> get softElevate => const [
        BoxShadow(
          color: Color(0x0F000000), // ~0.06
          blurRadius: 16,
          offset: Offset(0, 4),
        ),
      ];
}
