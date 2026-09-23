import 'dart:async';

import 'package:flutter/material.dart';

import '../api/device_session.dart';
import '../api/issues_api.dart';
import '../api/models.dart';
import '../api/pipeline_api.dart';
import '../api/settings_api.dart';
import '../theme/takeley_colors.dart';
import '../utils/industries.dart';
import '../widgets/data_state.dart';
import '../widgets/feed_chips.dart';
import '../widgets/issue_card.dart';
import '../widgets/page_header.dart';

final _feedTabs = <({String id, String label})>[
  (id: 'all', label: '전체'),
  ...kIssueIndustries.map((id) => (id: id, label: id)),
];

/// Mirrors `frontend/src/screens/HomeScreen.tsx`.
class HomeScreen extends StatefulWidget {
  const HomeScreen({
    super.key,
    required this.issuesApi,
    required this.settingsApi,
    required this.pipelineApi,
    required this.session,
    required this.onIssueOpen,
  });

  final IssuesApi issuesApi;
  final SettingsApi settingsApi;
  final PipelineApi pipelineApi;
  final DeviceSession session;
  final ValueChanged<String> onIssueOpen;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  String _tab = 'all';
  List<Issue> _items = [];
  bool _loading = true;
  bool _collecting = false;
  String? _error;
  String? _displayName;

  @override
  void initState() {
    super.initState();
    _loadSettings();
    _loadFeed();
  }

  Future<void> _loadSettings() async {
    try {
      final s = await widget.settingsApi.fetch(userId: widget.session.userId);
      if (!mounted) return;
      setState(() => _displayName = s.displayName);
    } catch (_) {}
  }

  Future<void> _refreshPipeline() async {
    try {
      final status = await widget.pipelineApi.fetchStatus();
      if (!mounted) return;
      setState(() => _collecting = status.collecting);
    } catch (_) {}
  }

  Future<void> _loadFeed({bool quiet = false}) async {
    if (!quiet) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final userId = widget.session.userId;
      final category = _tab == 'all' ? null : _tab;
      await _refreshPipeline();
      final result = await widget.issuesApi.fetchIssues(
        limit: 40,
        sort: 'trending',
        category: category,
        userId: userId,
      );

      if (!mounted) return;
      setState(() {
        _items = result.items;
        _loading = false;
      });

      for (final issue in result.items.take(12)) {
        unawaited(widget.issuesApi
            .recordEvent(id: issue.id, event: 'impression', userId: userId));
      }
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = '이슈를 불러오지 못했어요.\n잠시 후 다시 시도해 주세요.';
      });
    }
  }

  String get _title {
    final name = (_displayName ?? '').trim();
    if (name.isEmpty) return '오늘의 이슈';
    final hour = DateTime.now().hour;
    final phrase = hour >= 5 && hour < 12
        ? '좋은 아침이에요'
        : hour >= 12 && hour < 17
            ? '좋은 오후예요'
            : hour >= 17 && hour < 21
                ? '좋은 저녁이에요'
                : '좋은 밤이에요';
    return '👋 $phrase, $name';
  }

  @override
  Widget build(BuildContext context) {
    final showTopBar = !_loading && _collecting && _items.isNotEmpty;

    return RefreshIndicator(
      color: TakeleyColors.accent,
      onRefresh: () => _loadFeed(),
      child: CustomScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        slivers: [
          SliverToBoxAdapter(
            child: PageHeader(title: _title),
          ),
          if (showTopBar)
            const SliverToBoxAdapter(
              child: Padding(
                padding: EdgeInsets.fromLTRB(20, 0, 20, 8),
                child: Text(
                  '소식을 모으는 중…',
                  style: TextStyle(
                    color: TakeleyColors.muted,
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: FeedChips(
                tabs: _feedTabs,
                selectedId: _tab,
                onSelect: (id) {
                  setState(() => _tab = id);
                  _loadFeed();
                },
              ),
            ),
          ),
          if (_loading)
            const SliverFillRemaining(
              hasScrollBody: false,
              child: Center(
                child: CircularProgressIndicator(color: TakeleyColors.accent),
              ),
            )
          else if (_error != null)
            SliverFillRemaining(
              hasScrollBody: false,
              child: DataState(
                message: _error!,
                actionLabel: '다시 시도',
                onAction: () => _loadFeed(),
              ),
            )
          else if (_items.isEmpty)
            SliverFillRemaining(
              hasScrollBody: false,
              child: DataState(
                message: _collecting
                    ? '소식을 모으는 중\n인터넷에서 이슈를 찾고 있어요.'
                    : '아직 이슈가 없어요.',
              ),
            )
          else
            SliverList.separated(
              itemCount: _items.length,
              separatorBuilder: (_, __) => const Padding(
                padding: EdgeInsets.symmetric(horizontal: 20),
                child: Divider(height: 1, thickness: 2),
              ),
              itemBuilder: (context, index) {
                final issue = _items[index];
                return IssueCard(
                  issue: issue,
                  onOpen: (i) => widget.onIssueOpen(i.id),
                );
              },
            ),
          const SliverToBoxAdapter(child: SizedBox(height: 24)),
        ],
      ),
    );
  }
}
