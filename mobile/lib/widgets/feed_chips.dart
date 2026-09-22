import 'package:flutter/material.dart';

import '../theme/takeley_colors.dart';

/// React `.home-feed-chip` / `.is-active` — white outline → solid accent fill.
class FeedChips extends StatelessWidget {
  const FeedChips({
    super.key,
    required this.tabs,
    required this.selectedId,
    required this.onSelect,
  });

  final List<({String id, String label})> tabs;
  final String selectedId;
  final ValueChanged<String> onSelect;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 40,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.fromLTRB(20, 2, 20, 6),
        itemCount: tabs.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final tab = tabs[index];
          final active = tab.id == selectedId;
          return GestureDetector(
            onTap: () => onSelect(tab.id),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              curve: const Cubic(0.32, 0.72, 0, 1),
              padding: const EdgeInsets.symmetric(horizontal: 14.4, vertical: 7.2),
              decoration: BoxDecoration(
                color: active ? TakeleyColors.accent : TakeleyColors.canvas,
                borderRadius: BorderRadius.circular(999),
                border: Border.all(
                  color: active ? TakeleyColors.accent : TakeleyColors.hairline,
                ),
              ),
              child: Text(
                tab.label,
                style: TextStyle(
                  color: active
                      ? Colors.white
                      : const Color(0xFF444444),
                  fontWeight: FontWeight.w600,
                  fontSize: 14,
                  letterSpacing: -0.28,
                  height: 1.2,
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}
