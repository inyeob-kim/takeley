import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

/// Reloads when a StatefulShell tab becomes the active location again.
///
/// React remounts tab screens on every visit; Flutter keeps shell branches alive.
mixin TabVisibilityReloadMixin<T extends StatefulWidget> on State<T> {
  GoRouter? _tabRouter;
  String? _tabLastPath;
  bool _tabListening = false;

  /// Path segment that identifies this tab (e.g. `/activity`, `/profile`).
  String get tabPath;

  /// Called when navigating onto [tabPath] from another location.
  void onTabBecameVisible();

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final router = GoRouter.of(context);
    if (!identical(_tabRouter, router)) {
      _detachTabListener();
      _tabRouter = router;
      _tabLastPath = _currentPath(router);
      _tabRouter!.routerDelegate.addListener(_onTabRoute);
      _tabListening = true;
    }
  }

  @override
  void dispose() {
    _detachTabListener();
    super.dispose();
  }

  void _detachTabListener() {
    if (_tabListening && _tabRouter != null) {
      _tabRouter!.routerDelegate.removeListener(_onTabRoute);
      _tabListening = false;
    }
    _tabRouter = null;
  }

  String _currentPath(GoRouter router) {
    try {
      return router.routerDelegate.currentConfiguration.uri.path;
    } catch (_) {
      return '';
    }
  }

  bool _matchesTab(String path) {
    final target = tabPath.endsWith('/')
        ? tabPath.substring(0, tabPath.length - 1)
        : tabPath;
    return path == target || path.endsWith(target);
  }

  void _onTabRoute() {
    final router = _tabRouter;
    if (router == null || !mounted) return;
    final path = _currentPath(router);
    final now = _matchesTab(path);
    final was = _tabLastPath != null && _matchesTab(_tabLastPath!);
    _tabLastPath = path;
    if (now && !was) {
      onTabBecameVisible();
    }
  }
}
