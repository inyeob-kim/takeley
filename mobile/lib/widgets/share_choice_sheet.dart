import 'package:flutter/material.dart';

import '../theme/takeley_colors.dart';
import 'takeley_buttons.dart';

/// TAKELEY-toned share intent picker (not Material ListTiles).
Future<bool?> showShareChoiceSheet(
  BuildContext context, {
  required String takeLabel,
}) {
  return showModalBottomSheet<bool>(
    context: context,
    backgroundColor: TakeleyColors.canvas,
    showDragHandle: true,
    useSafeArea: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (context) => _ShareChoiceSheet(takeLabel: takeLabel),
  );
}

class _ShareChoiceSheet extends StatelessWidget {
  const _ShareChoiceSheet({required this.takeLabel});

  final String takeLabel;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 4, 20, 28),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '공유',
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w800,
              letterSpacing: -0.4,
              color: TakeleyColors.fg,
              height: 1.25,
            ),
          ),
          const SizedBox(height: 6),
          const Text(
            '상대방에게 이슈 카드가 보여요.',
            style: TextStyle(
              fontSize: 15,
              height: 1.45,
              color: TakeleyColors.muted,
            ),
          ),
          const SizedBox(height: 20),
          TakeleyOffsetPillButton(
            label: '이 이슈, 너는 어떻게 생각해?',
            onPressed: () => Navigator.pop(context, false),
          ),
          const SizedBox(height: 10),
          TakeleySecondaryPillButton(
            label: takeLabel.isEmpty
                ? '내 의견 포함해서 공유'
                : '‘$takeLabel’로 공유',
            onPressed: () => Navigator.pop(context, true),
          ),
        ],
      ),
    );
  }
}
