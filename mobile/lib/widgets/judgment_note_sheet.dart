import 'package:flutter/material.dart';

import '../theme/takeley_colors.dart';
import 'takeley_buttons.dart';

/// Optional one-line judgment note — calm sheet, not a comment thread.
Future<String?> showJudgmentNoteSheet(
  BuildContext context, {
  String? initialNote,
}) {
  return showModalBottomSheet<String>(
    context: context,
    backgroundColor: TakeleyColors.canvas,
    showDragHandle: true,
    useSafeArea: true,
    isScrollControlled: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (context) => _JudgmentNoteSheet(initialNote: initialNote ?? ''),
  );
}

class _JudgmentNoteSheet extends StatefulWidget {
  const _JudgmentNoteSheet({required this.initialNote});

  final String initialNote;

  @override
  State<_JudgmentNoteSheet> createState() => _JudgmentNoteSheetState();
}

class _JudgmentNoteSheetState extends State<_JudgmentNoteSheet> {
  late final TextEditingController _ctrl;
  static const _max = 120;

  @override
  void initState() {
    super.initState();
    _ctrl = TextEditingController(text: widget.initialNote);
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  void _submit() {
    final text = _ctrl.text.trim();
    if (text.isEmpty) return;
    Navigator.pop(context, text);
  }

  @override
  Widget build(BuildContext context) {
    final inset = MediaQuery.viewInsetsOf(context).bottom;
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 4, 20, 28 + inset),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '한 줄로 남겨두기',
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
            '댓글이 아니에요. 나중에 볼 나의 판단이에요.',
            style: TextStyle(
              fontSize: 15,
              height: 1.45,
              color: TakeleyColors.muted,
            ),
          ),
          const SizedBox(height: 18),
          TextField(
            controller: _ctrl,
            autofocus: true,
            maxLength: _max,
            maxLines: 3,
            minLines: 2,
            textInputAction: TextInputAction.done,
            onSubmitted: (_) => _submit(),
            onTapOutside: (_) => FocusManager.instance.primaryFocus?.unfocus(),
            decoration: const InputDecoration(
              hintText: '예: 비용이 결국 서민에게 갈 것 같아서',
            ),
          ),
          const SizedBox(height: 12),
          TakeleyOffsetPillButton(
            label: '남기기',
            onPressed: _submit,
          ),
          const SizedBox(height: 8),
          TakeleySecondaryPillButton(
            label: '다음에',
            onPressed: () => Navigator.pop(context),
          ),
        ],
      ),
    );
  }
}
