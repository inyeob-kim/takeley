import 'package:flutter/material.dart';

import '../api/models.dart';
import '../theme/takeley_colors.dart';
import 'takeley_buttons.dart';

/// Daily judgment recap — same sheet chrome as share / judgment note.
Future<void> showRecapSheet(
  BuildContext context, {
  required RecapToday recap,
  VoidCallback? onClosed,
}) {
  return showModalBottomSheet<void>(
    context: context,
    backgroundColor: TakeleyColors.canvas,
    showDragHandle: true,
    useSafeArea: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (context) => _RecapSheet(recap: recap, onClosed: onClosed),
  );
}

String _softStreakLine(int days) {
  if (days <= 1) return '';
  if (days == 2) return '이틀째예요';
  if (days == 3) return '사흘째예요';
  return '$days일째예요';
}

class _RecapSheet extends StatelessWidget {
  const _RecapSheet({required this.recap, this.onClosed});

  final RecapToday recap;
  final VoidCallback? onClosed;

  @override
  Widget build(BuildContext context) {
    final softStreak = _softStreakLine(recap.streakDays);
    final subtitle = softStreak.isEmpty
        ? '나중에 다시 볼 오늘의 판단이에요'
        : '나중에 다시 볼 오늘의 판단이에요. $softStreak';

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 4, 20, 28),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '오늘, 이렇게 봤어요',
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w800,
              letterSpacing: -0.4,
              color: TakeleyColors.fg,
              height: 1.25,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            subtitle,
            style: const TextStyle(
              fontSize: 15,
              height: 1.45,
              color: TakeleyColors.muted,
            ),
          ),
          const SizedBox(height: 20),
          ...recap.items.take(5).map(
                (e) => Padding(
                  padding: const EdgeInsets.only(bottom: 14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        e.title,
                        style: const TextStyle(
                          fontSize: 15,
                          height: 1.35,
                          fontWeight: FontWeight.w600,
                          color: TakeleyColors.fg,
                        ),
                      ),
                      if (e.optionLabel.isNotEmpty) ...[
                        const SizedBox(height: 4),
                        Text(
                          e.optionLabel,
                          style: const TextStyle(
                            fontSize: 13,
                            height: 1.35,
                            fontWeight: FontWeight.w500,
                            color: TakeleyColors.muted,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
          const SizedBox(height: 6),
          TakeleySecondaryPillButton(
            label: '닫기',
            minHeight: 52,
            fontSize: 16,
            onPressed: () {
              Navigator.of(context).pop();
              onClosed?.call();
            },
          ),
        ],
      ),
    );
  }
}
