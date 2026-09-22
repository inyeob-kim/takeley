import 'package:flutter/material.dart';

import '../theme/takeley_colors.dart';

/// Shared Finimize/React language: white screen + gray `#f2f2f7` pills.
class ProfileBlockLabel extends StatelessWidget {
  const ProfileBlockLabel(this.text, {super.key});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(3, 0, 3, 9),
      child: Text(
        text,
        style: const TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          color: TakeleyColors.secondaryLabel,
        ),
      ),
    );
  }
}

class ProfilePillRow extends StatelessWidget {
  const ProfilePillRow({
    super.key,
    required this.icon,
    required this.label,
    this.count,
    this.value,
    this.trailing,
    this.onTap,
  });

  final IconData icon;
  final String label;
  final int? count;
  final String? value;
  final Widget? trailing;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final child = Container(
      constraints: const BoxConstraints(minHeight: 56),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
      decoration: BoxDecoration(
        color: TakeleyColors.pill,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 28,
            height: 28,
            child: Icon(icon, size: 20, color: TakeleyColors.fg),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              label,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                letterSpacing: -0.3,
                color: TakeleyColors.fg,
              ),
            ),
          ),
          if (trailing != null)
            trailing!
          else ...[
            if (count != null || value != null)
              Text(
                value ?? '$count',
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w500,
                  color: TakeleyColors.secondaryLabel,
                ),
              ),
            if (onTap != null) ...[
              const SizedBox(width: 2),
              const Text(
                '›',
                style: TextStyle(
                  fontSize: 22,
                  height: 1,
                  color: TakeleyColors.chevron,
                  fontWeight: FontWeight.w400,
                ),
              ),
            ],
          ],
        ],
      ),
    );

    if (onTap == null) {
      return Padding(padding: const EdgeInsets.only(bottom: 9), child: child);
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 9),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: child,
        ),
      ),
    );
  }
}

/// Shared screen header title — matches profile / settings top bar (17 Bold).
class TakeleyHeaderStyle {
  TakeleyHeaderStyle._();

  static const TextStyle title = TextStyle(
    fontWeight: FontWeight.w700,
    fontSize: 17,
    letterSpacing: -0.3,
    height: 1.3,
    color: TakeleyColors.fg,
  );
}

/// Sticky top bar matching React `.profile-topbar` / `.settings-topbar`.
///
/// React settings body starts with `0.85rem` (~14px) under the hairline.
class ScreenTopBar extends StatelessWidget {
  const ScreenTopBar({
    super.key,
    required this.title,
    this.leading,
    this.trailing,
    this.afterGap = 14,
  });

  final String title;
  final Widget? leading;
  final Widget? trailing;
  final double afterGap;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          padding: const EdgeInsets.fromLTRB(8, 4, 8, 8),
          decoration: const BoxDecoration(
            color: Color(0xF5FFFFFF),
            border: Border(
              bottom: BorderSide(color: TakeleyColors.border, width: 1),
            ),
          ),
          child: SizedBox(
            height: 44,
            child: Row(
              children: [
                SizedBox(
                  width: 44,
                  child: leading ?? const SizedBox.shrink(),
                ),
                Expanded(
                  child: Text(
                    title,
                    textAlign: TextAlign.center,
                    style: TakeleyHeaderStyle.title,
                  ),
                ),
                SizedBox(
                  width: 44,
                  child: trailing ?? const SizedBox.shrink(),
                ),
              ],
            ),
          ),
        ),
        if (afterGap > 0) SizedBox(height: afterGap),
      ],
    );
  }
}
