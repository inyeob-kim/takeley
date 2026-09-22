import 'package:flutter/material.dart';

import '../theme/takeley_colors.dart';
import 'profile_chrome.dart';

/// Sticky page title — same type size as profile / settings header (17 Bold).
///
/// React: `margin-bottom: 1.5rem` after the hairline so body content breathes.
class PageHeader extends StatelessWidget {
  const PageHeader({
    super.key,
    required this.title,
    this.subtitle,
    this.trailing,
  });

  /// Gap below the border before feed/chips — matches React `1.5rem`.
  static const double afterGap = 24;

  final String title;
  final String? subtitle;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 14),
          decoration: const BoxDecoration(
            color: Color(0xF2FFFFFF),
            border: Border(
              bottom: BorderSide(color: TakeleyColors.border, width: 1),
            ),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(
                        title,
                        style: TakeleyHeaderStyle.title,
                      ),
                    ),
                    if (subtitle != null && subtitle!.isNotEmpty) ...[
                      const SizedBox(height: 6),
                      Text(
                        subtitle!,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: TakeleyColors.muted,
                            ),
                      ),
                    ],
                  ],
                ),
              ),
              if (trailing != null) trailing!,
            ],
          ),
        ),
        const SizedBox(height: afterGap),
      ],
    );
  }
}
