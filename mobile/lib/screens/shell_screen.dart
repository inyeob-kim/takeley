import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../theme/takeley_colors.dart';
import '../widgets/phone_frame.dart';

/// Mirrors `frontend/src/App.tsx` tab chrome (홈 / 내 이슈 / 프로필).
class ShellScreen extends StatelessWidget {
  const ShellScreen({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context) {
    final index = navigationShell.currentIndex;
    return PhoneFrame(
      child: Scaffold(
        backgroundColor: TakeleyColors.canvas,
        body: SafeArea(
          bottom: false,
          child: navigationShell,
        ),
        bottomNavigationBar: DecoratedBox(
          decoration: const BoxDecoration(
            border: Border(top: BorderSide(color: TakeleyColors.border)),
            color: TakeleyColors.canvas,
          ),
          child: SafeArea(
            top: false,
            child: SizedBox(
              height: 56,
              child: Row(
                children: [
                  _TabItem(
                    label: '홈',
                    active: index == 0,
                    icon: Icons.home_rounded,
                    onTap: () => navigationShell.goBranch(0),
                  ),
                  _TabItem(
                    label: '내 이슈',
                    active: index == 1,
                    icon: Icons.pie_chart_rounded,
                    onTap: () => navigationShell.goBranch(1),
                  ),
                  _TabItem(
                    label: '프로필',
                    active: index == 2,
                    icon: Icons.person_outline_rounded,
                    onTap: () => navigationShell.goBranch(2),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _TabItem extends StatelessWidget {
  const _TabItem({
    required this.label,
    required this.active,
    required this.icon,
    required this.onTap,
  });

  final String label;
  final bool active;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = active ? TakeleyColors.accent : TakeleyColors.fg;
    return Expanded(
      child: InkWell(
        onTap: onTap,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 26, color: color),
            const SizedBox(height: 2),
            Text(
              label,
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: color,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
