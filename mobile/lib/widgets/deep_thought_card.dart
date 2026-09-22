import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../api/contributor_api.dart';
import '../theme/takeley_colors.dart';
import '../utils/contributor_ui.dart';

/// Compact deep-thought preview card (issue detail + full list).
class DeepThoughtCard extends StatelessWidget {
  const DeepThoughtCard({
    super.key,
    required this.take,
    required this.onTap,
  });

  final IssueTake take;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final fmt = NumberFormat.decimalPattern('ko_KR');
    final name = (take.displayName ?? '').trim();
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Material(
        color: TakeleyColors.canvas,
        borderRadius: BorderRadius.circular(14),
        child: InkWell(
          borderRadius: BorderRadius.circular(14),
          onTap: onTap,
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(14),
              border: Border.all(
                color: Colors.black.withValues(alpha: 0.08),
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Contributor',
                  style: Theme.of(context)
                      .textTheme
                      .labelLarge
                      ?.copyWith(color: TakeleyColors.accent),
                ),
                const SizedBox(height: 4),
                Text(
                  name.isEmpty ? '익명' : name,
                  style: const TextStyle(
                    color: TakeleyColors.muted,
                    fontSize: 13,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  take.title,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 17,
                    color: TakeleyColors.fg,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  previewBody(take.body),
                  style: const TextStyle(
                    color: TakeleyColors.muted,
                    height: 1.45,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  '조회 ${fmt.format(take.viewCount)} · 공감 ${fmt.format(take.reactionCount)}',
                  style: const TextStyle(
                    color: TakeleyColors.muted,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
