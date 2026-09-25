import 'package:flutter/material.dart';

import '../api/safety_api.dart';
import '../theme/takeley_colors.dart';
import 'takeley_buttons.dart';

const kUgcReportReasons = <(String, String)>[
  ('hate', '혐오·차별'),
  ('sexual', '음란·성적'),
  ('violence', '폭력·위협'),
  ('spam', '스팸'),
  ('other', '기타'),
];

Future<T?> _showTakeleyChoiceSheet<T>({
  required BuildContext context,
  required String title,
  required String subtitle,
  required List<(String label, T value)> options,
}) {
  return showModalBottomSheet<T>(
    context: context,
    backgroundColor: TakeleyColors.canvas,
    showDragHandle: true,
    useSafeArea: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (ctx) {
      return Padding(
        padding: const EdgeInsets.fromLTRB(20, 4, 20, 28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: const TextStyle(
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
            for (var i = 0; i < options.length; i++) ...[
              if (i > 0) const SizedBox(height: 10),
              i == 0 && options.length == 1
                  ? TakeleyOffsetPillButton(
                      label: options[i].$1,
                      onPressed: () => Navigator.pop(ctx, options[i].$2),
                    )
                  : TakeleySecondaryPillButton(
                      label: options[i].$1,
                      minHeight: 52,
                      fontSize: 16,
                      onPressed: () => Navigator.pop(ctx, options[i].$2),
                    ),
            ],
          ],
        ),
      );
    },
  );
}

Future<void> showUgcActions({
  required BuildContext context,
  required SafetyApi safetyApi,
  required String targetType,
  required String targetId,
  required String authorId,
  required String? viewerId,
  required bool isMine,
  required VoidCallback onRemovedFromFeed,
  Future<void> Function()? onDeleteOwn,
}) async {
  final noun = targetType == 'take' ? '생각' : '댓글';
  final String? action;
  if (isMine && onDeleteOwn != null) {
    action = await _showTakeleyChoiceSheet<String>(
      context: context,
      title: '내 $noun',
      subtitle: '삭제한 글은 피드에서 바로 사라져요.',
      options: const [('삭제', 'delete')],
    );
  } else {
    action = await _showTakeleyChoiceSheet<String>(
      context: context,
      title: '이 $noun',
      subtitle: '신고하면 24시간 안에 검토하고, 숨기거나 차단하면 바로 안 보여요.',
      options: const [
        ('신고하기', 'report'),
        ('이 글 숨기기', 'hide'),
        ('이 사용자 차단', 'block'),
      ],
    );
  }
  if (!context.mounted || action == null) return;

  try {
    if (action == 'delete') {
      await onDeleteOwn?.call();
      onRemovedFromFeed();
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('글을 삭제했어요.')),
      );
      return;
    }
    if (action == 'report') {
      final reason = await _showTakeleyChoiceSheet<String>(
        context: context,
        title: '어떤 내용인가요?',
        subtitle: '신고하면 이 글은 내 피드에서 바로 사라져요.',
        options: [for (final item in kUgcReportReasons) (item.$2, item.$1)],
      );
      if (!context.mounted || reason == null) return;
      await safetyApi.report(
        targetType: targetType,
        targetId: targetId,
        reason: reason,
        userId: viewerId,
      );
    } else if (action == 'hide') {
      await safetyApi.hide(
        targetType: targetType,
        targetId: targetId,
        userId: viewerId,
      );
    } else if (action == 'block') {
      await safetyApi.blockUser(
        blockedUserId: authorId,
        userId: viewerId,
      );
    }
    if (!context.mounted) return;
    onRemovedFromFeed();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          action == 'block'
              ? '이 사용자의 글을 더 이상 보지 않아요.'
              : action == 'report'
                  ? '신고했어요. 24시간 안에 검토합니다.'
                  : '피드에서 숨겼어요.',
        ),
      ),
    );
  } catch (_) {
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('처리하지 못했어요. 잠시 후 다시 시도해 주세요.')),
    );
  }
}
