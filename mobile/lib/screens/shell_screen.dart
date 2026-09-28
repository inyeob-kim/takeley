import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../theme/takeley_colors.dart';
import '../widgets/phone_frame.dart';

/// Same-tab 홈 탭: scroll-to-top + refresh. HomeScreen listens.
class HomeRetapScope extends InheritedWidget {
  const HomeRetapScope({
    super.key,
    required this.notifier,
    required super.child,
  });

  final ValueNotifier<int> notifier;

  static ValueNotifier<int>? maybeOf(BuildContext context) {
    return context
        .dependOnInheritedWidgetOfExactType<HomeRetapScope>()
        ?.notifier;
  }

  @override
  bool updateShouldNotify(HomeRetapScope oldWidget) =>
      notifier != oldWidget.notifier;
}

/// Mirrors `frontend/src/App.tsx` tab chrome (홈 / 내 이슈 / 프로필).
class ShellScreen extends StatefulWidget {
  const ShellScreen({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  State<ShellScreen> createState() => _ShellScreenState();
}

class _ShellScreenState extends State<ShellScreen> {
  final ValueNotifier<int> _homeRetap = ValueNotifier<int>(0);

  @override
  void dispose() {
    _homeRetap.dispose();
    super.dispose();
  }

  void _tapHome() {
    if (widget.navigationShell.currentIndex == 0) {
      _homeRetap.value++;
      return;
    }
    widget.navigationShell.goBranch(0);
  }

  @override
  Widget build(BuildContext context) {
    final index = widget.navigationShell.currentIndex;
    return HomeRetapScope(
      notifier: _homeRetap,
      child: PhoneFrame(
        child: Scaffold(
          backgroundColor: TakeleyColors.canvas,
          body: SafeArea(
            bottom: false,
            child: widget.navigationShell,
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
                      onTap: _tapHome,
                    ),
                    _TabItem(
                      label: '내 이슈',
                      active: index == 1,
                      icon: Icons.pie_chart_rounded,
                      onTap: () => widget.navigationShell.goBranch(1),
                    ),
                    _TabItem(
                      label: '프로필',
                      active: index == 2,
                      icon: Icons.person_outline_rounded,
                      onTap: () => widget.navigationShell.goBranch(2),
                    ),
                  ],
                ),
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
