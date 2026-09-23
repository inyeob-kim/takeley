import 'dart:async';

import 'package:app_links/app_links.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'api/api_client.dart';
import 'api/contributor_api.dart';
import 'api/device_session.dart';
import 'api/issues_api.dart';
import 'api/pipeline_api.dart';
import 'api/settings_api.dart';
import 'navigation/deep_link.dart';
import 'navigation/page_transitions.dart';
import 'screens/activity_screen.dart';
import 'screens/home_screen.dart';
import 'screens/issue_detail_screen.dart';
import 'screens/profile_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/shell_screen.dart';
import 'services/fcm_service.dart';
import 'theme/takeley_theme.dart';
import 'widgets/phone_frame.dart';

class TakeleyApp extends StatefulWidget {
  const TakeleyApp({
    super.key,
    required this.api,
    required this.session,
    required this.fcm,
  });

  final ApiClient api;
  final DeviceSession session;
  final FcmService fcm;

  @override
  State<TakeleyApp> createState() => _TakeleyAppState();
}

class _TakeleyAppState extends State<TakeleyApp> {
  late final IssuesApi _issuesApi = IssuesApi(widget.api);
  late final ContributorApi _contributorApi = ContributorApi(widget.api);
  late final SettingsApi _settingsApi = SettingsApi(widget.api);
  late final PipelineApi _pipelineApi = PipelineApi(widget.api);
  late final GoRouter _router;
  final AppLinks _appLinks = AppLinks();
  StreamSubscription<Uri>? _linkSub;

  @override
  void initState() {
    super.initState();
    _router = _buildRouter();
    widget.fcm.onOpened = _handleDeepLink;
    unawaited(_initAppLinks());
  }

  Future<void> _initAppLinks() async {
    try {
      final initial = await _appLinks.getInitialLink();
      if (initial != null) {
        _handleDeepLink(parseDeepLink(initial.toString()));
      }
    } catch (_) {
      /* cold-start link unavailable */
    }
    _linkSub = _appLinks.uriLinkStream.listen((uri) {
      _handleDeepLink(parseDeepLink(uri.toString()));
    });
  }

  @override
  void dispose() {
    _linkSub?.cancel();
    super.dispose();
  }

  void _handleDeepLink(DeepLinkTarget? target) {
    switch (target) {
      case SignalLink(
          :final signalId,
          :final shareId,
          :final refUserId,
        ):
        _router.go(
          issueRoutePath(
            SignalLink(signalId, shareId: shareId, refUserId: refUserId),
          ),
        );
      case SettingsLink():
        _router.go('/settings');
      case BriefLink():
      case HomeLink():
      case null:
        _router.go('/home');
    }
  }

  void _openIssue(
    BuildContext context,
    String id, {
    IssueDeepFocus? focus,
  }) {
    context.push('/issues/$id', extra: focus);
  }

  GoRouter _buildRouter() {
    return GoRouter(
      initialLocation: '/home',
      redirect: (context, state) {
        final mapped = routerLocationForUri(state.uri);
        if (mapped != null) return mapped;
        final path = state.uri.path;
        if (path.isEmpty || path == '/') return '/home';
        return null;
      },
      onException: (context, state, router) {
        final mapped = routerLocationForUri(state.uri);
        router.go(mapped ?? '/home');
      },
      routes: [
        StatefulShellRoute.indexedStack(
          builder: (context, state, navigationShell) {
            return ShellScreen(navigationShell: navigationShell);
          },
          branches: [
            StatefulShellBranch(
              routes: [
                GoRoute(
                  path: '/home',
                  builder: (context, state) => HomeScreen(
                    issuesApi: _issuesApi,
                    settingsApi: _settingsApi,
                    pipelineApi: _pipelineApi,
                    session: widget.session,
                    onIssueOpen: (id) => _openIssue(context, id),
                  ),
                ),
              ],
            ),
            StatefulShellBranch(
              routes: [
                GoRoute(
                  path: '/activity',
                  builder: (context, state) => ActivityScreen(
                    issuesApi: _issuesApi,
                    session: widget.session,
                    onIssueOpen: (id) => _openIssue(context, id),
                    onDeepThoughtOpen: (issueId, focus) =>
                        _openIssue(context, issueId, focus: focus),
                  ),
                ),
              ],
            ),
            StatefulShellBranch(
              routes: [
                GoRoute(
                  path: '/profile',
                  builder: (context, state) => ProfileScreen(
                    settingsApi: _settingsApi,
                    issuesApi: _issuesApi,
                    session: widget.session,
                    onOpenSettings: () => context.push('/settings'),
                    onOpenActivity: () => context.go('/activity'),
                  ),
                ),
              ],
            ),
          ],
        ),
        GoRoute(
          path: '/issues/:id',
          pageBuilder: (context, state) {
            final id = state.pathParameters['id'] ?? '';
            final focus = state.extra is IssueDeepFocus
                ? state.extra as IssueDeepFocus
                : null;
            final sid = state.uri.queryParameters['sid'] ??
                state.uri.queryParameters['share_id'];
            final ref = state.uri.queryParameters['ref'];
            return takeleySlidePage(
              key: state.pageKey,
              child: PhoneFrame(
                child: IssueDetailScreen(
                  issueId: id,
                  issuesApi: _issuesApi,
                  contributorApi: _contributorApi,
                  session: widget.session,
                  initialDeepFocus: focus,
                  shareId: (sid != null && sid.isNotEmpty) ? sid : null,
                  refUserId: (ref != null && ref.isNotEmpty) ? ref : null,
                  onBack: () {
                    if (context.canPop()) {
                      context.pop();
                    } else {
                      context.go('/home');
                    }
                  },
                ),
              ),
            );
          },
        ),
        GoRoute(
          path: '/settings',
          pageBuilder: (context, state) {
            return takeleySheetPage(
              key: state.pageKey,
              child: PhoneFrame(
                child: SettingsScreen(
                  settingsApi: _settingsApi,
                  contributorApi: _contributorApi,
                  session: widget.session,
                  fcm: widget.fcm,
                  onBack: () {
                    if (context.canPop()) {
                      context.pop();
                    } else {
                      context.go('/profile');
                    }
                  },
                ),
              ),
            );
          },
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'TAKELEY',
      debugShowCheckedModeBanner: false,
      theme: buildTakeleyTheme(),
      routerConfig: _router,
    );
  }
}
