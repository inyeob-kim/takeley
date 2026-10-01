import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/device_session.dart';
import '../api/issues_api.dart';
import '../api/models.dart';
import '../api/pipeline_api.dart';
import '../api/settings_api.dart';
import '../theme/takeley_colors.dart';
import '../widgets/data_state.dart';
import '../widgets/issue_card.dart';
import '../widgets/page_header.dart';
import 'shell_screen.dart';

/// Home IA: 오늘의 TAKE (priority) → 오늘의 뉴스 (capped preview).
/// Category chips live on the NEWS browse screen, not here.
class HomeScreen extends StatefulWidget {
  const HomeScreen({
    super.key,
    required this.issuesApi,
    required this.settingsApi,
    required this.pipelineApi,
    required this.session,
    required this.onIssueOpen,
    this.onIssueTake,
  });

  final IssuesApi issuesApi;
  final SettingsApi settingsApi;
  final PipelineApi pipelineApi;
  final DeviceSession session;
  final void Function(String id, {bool scrollToTake}) onIssueOpen;
  final ValueChanged<String>? onIssueTake;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  static const _issuePreviewLimit = 3;
  static const _newsPreviewLimit = 5;

  List<Issue> _issues = [];
  List<Issue> _news = [];
  ClosureItem? _closure;
  bool _loading = true;
  bool _collecting = false;
  String? _error;
  String? _displayName;
  final ScrollController _scroll = ScrollController();
  ValueNotifier<int>? _homeRetap;
  bool _recapChecked = false;

  @override
  void initState() {
    super.initState();
    _loadSettings();
    _loadFeed();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final retap = HomeRetapScope.maybeOf(context);
    if (identical(retap, _homeRetap)) return;
    _homeRetap?.removeListener(_onHomeTabRetap);
    _homeRetap = retap;
    _homeRetap?.addListener(_onHomeTabRetap);
  }

  @override
  void dispose() {
    _homeRetap?.removeListener(_onHomeTabRetap);
    _scroll.dispose();
    super.dispose();
  }

  void _onHomeTabRetap() {
    if (!mounted) return;
    if (_scroll.hasClients) {
      unawaited(
        _scroll.animateTo(
          0,
          duration: const Duration(milliseconds: 280),
          curve: Curves.easeOutCubic,
        ),
      );
    }
    unawaited(_loadFeed(quiet: true));
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
      await _refreshPipeline();
      final results = await Future.wait([
        widget.issuesApi.fetchIssues(
          limit: _issuePreviewLimit,
          sort: 'trending',
          contentKind: 'ISSUE',
          userId: userId,
        ),
        widget.issuesApi.fetchIssues(
          limit: _newsPreviewLimit,
          sort: 'new',
          contentKind: 'NEWS',
          userId: userId,
        ),
      ]);

      if (!mounted) return;
      // Defend against older APIs that ignore content_kind (same list twice).
      final issues = results[0]
          .items
          .where((i) => i.contentKind == 'ISSUE')
          .toList();
      final news = results[1]
          .items
          .where((i) => i.contentKind == 'NEWS')
          .toList();
      setState(() {
        _issues = issues;
        _news = news;
        _loading = false;
      });

      for (final issue in [...issues, ...news].take(12)) {
        unawaited(widget.issuesApi
            .recordEvent(id: issue.id, event: 'impression', userId: userId));
      }
      unawaited(_loadClosure(userId));
      unawaited(_maybeShowRecap(userId));
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'TAKE를 불러오지 못했어요.\n잠시 후 다시 시도해 주세요.';
      });
    }
  }

  Future<void> _loadClosure(String? userId) async {
    try {
      final items = await widget.issuesApi.fetchClosures(userId: userId, limit: 1);
      if (!mounted) return;
      setState(() => _closure = items.isEmpty ? null : items.first);
    } catch (_) {}
  }

  Future<void> _maybeShowRecap(String? userId) async {
    if (_recapChecked) return;
    _recapChecked = true;
    try {
      final prefs = await SharedPreferences.getInstance();
      final today =
          '${DateTime.now().year}-${DateTime.now().month.toString().padLeft(2, '0')}-${DateTime.now().day.toString().padLeft(2, '0')}';
      final key = 'recap_shown_ymd';
      if (prefs.getString(key) == today) return;
      final recap = await widget.issuesApi.fetchRecapToday(userId: userId);
      if (!mounted || recap.items.isEmpty) return;
      await prefs.setString(key, today);
      if (!mounted) return;

      String streakLine(int days) {
        if (days <= 1) return '';
        if (days == 2) return '이틀째예요';
        if (days == 3) return '사흘째예요';
        return '$days일째예요';
      }

      final softStreak = streakLine(recap.streakDays);

      await showModalBottomSheet<void>(
        context: context,
        backgroundColor: TakeleyColors.canvas,
        showDragHandle: true,
        useSafeArea: true,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        builder: (ctx) {
          return Padding(
            padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '오늘, 이렇게 봤어요',
                  style: Theme.of(ctx).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                        letterSpacing: -0.3,
                      ),
                ),
                const SizedBox(height: 6),
                Text(
                  softStreak.isEmpty
                      ? '나중에 다시 볼 오늘의 판단이에요'
                      : '나중에 다시 볼 오늘의 판단이에요. $softStreak',
                  style: const TextStyle(
                    fontSize: 14,
                    height: 1.4,
                    color: TakeleyColors.secondaryLabel,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 18),
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
                                  color: TakeleyColors.muted,
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
                    ),
                const SizedBox(height: 4),
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: () {
                      Navigator.of(ctx).pop();
                      if (recap.items.isNotEmpty) {
                        unawaited(widget.issuesApi.recordEvent(
                          id: recap.items.first.issueId,
                          event: 'recap_viewed',
                          userId: userId,
                        ));
                      }
                    },
                    child: const Text('닫기'),
                  ),
                ),
              ],
            ),
          );
        },
      );
    } catch (_) {}
  }

  String get _title {
    final hour = DateTime.now().hour;
    final phrase = hour >= 5 && hour < 12
        ? '좋은 아침이에요'
        : hour >= 12 && hour < 17
            ? '좋은 오후예요'
            : hour >= 17 && hour < 21
                ? '좋은 저녁이에요'
                : '좋은 밤이에요';
    final name = (_displayName ?? '').trim();
    if (name.isEmpty) return '👋 $phrase';
    return '👋 $phrase, $name';
  }

  void _openCard(Issue i) {
    final canVote = i.contentKind.toUpperCase() != 'NEWS' &&
        i.participationSuitable &&
        (i.participationQuestion?.isNotEmpty ?? false);
    widget.onIssueOpen(i.id, scrollToTake: canVote);
  }

  void _ctaCard(Issue i) {
    final canVote = i.contentKind.toUpperCase() != 'NEWS' &&
        i.participationSuitable &&
        (i.participationQuestion?.isNotEmpty ?? false);
    if (canVote && widget.onIssueTake != null) {
      widget.onIssueTake!(i.id);
    } else {
      widget.onIssueOpen(i.id);
    }
  }

  @override
  Widget build(BuildContext context) {
    final showTopBar =
        !_loading && _collecting && (_issues.isNotEmpty || _news.isNotEmpty);

    return RefreshIndicator(
      color: TakeleyColors.accent,
      onRefresh: () => _loadFeed(),
      child: CustomScrollView(
        controller: _scroll,
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
          else ...[
            if (_closure != null)
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 4, 20, 12),
                  child: InkWell(
                    onTap: () => widget.onIssueOpen(_closure!.issueId),
                    borderRadius: BorderRadius.circular(12),
                    child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: TakeleyColors.soft,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            '정리된 이슈',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                              color: TakeleyColors.accent,
                            ),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            _closure!.title,
                            style: const TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          if (_closure!.optionLabel.isNotEmpty) ...[
                            const SizedBox(height: 4),
                            Text(
                              '내 입장 · ${_closure!.optionLabel}',
                              style: const TextStyle(
                                fontSize: 13,
                                color: TakeleyColors.muted,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ..._sectionSlivers(
              title: '오늘의 TAKE',
              moreLabel: 'TAKE 더보기 →',
              onMore: () => context.push('/home/issues'),
              items: _issues,
              emptyMessage: _collecting
                  ? '소식을 모으는 중\n인터넷에서 TAKE를 찾고 있어요.'
                  : '아직 TAKE가 없어요.',
            ),
            ..._sectionSlivers(
              title: '오늘의 뉴스',
              moreLabel: '뉴스 더보기 →',
              onMore: () => context.push('/home/news'),
              items: _news,
              emptyMessage: '아직 뉴스가 없어요.',
              leadWithSectionRule: true,
            ),
            const SliverToBoxAdapter(child: SizedBox(height: 24)),
          ],
        ],
      ),
    );
  }

  List<Widget> _sectionSlivers({
    required String title,
    required String moreLabel,
    required VoidCallback onMore,
    required List<Issue> items,
    required String emptyMessage,
    bool leadWithSectionRule = false,
  }) {
    return [
      if (leadWithSectionRule)
        const SliverToBoxAdapter(child: _NewsSectionRule()),
      SliverToBoxAdapter(
        child: _SectionHeader(
          title: title,
          moreLabel: moreLabel,
          onMore: onMore,
          topPadding: leadWithSectionRule ? 18 : 8,
        ),
      ),
      if (items.isEmpty)
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
            child: Text(
              emptyMessage,
              style: const TextStyle(
                color: TakeleyColors.muted,
                fontSize: 15,
                height: 1.45,
              ),
            ),
          ),
        )
      else
        SliverList.separated(
          itemCount: items.length,
          separatorBuilder: (_, __) => const Padding(
            padding: EdgeInsets.symmetric(horizontal: 20),
            child: Divider(height: 1, thickness: 2),
          ),
          itemBuilder: (context, index) {
            final issue = items[index];
            return IssueCard(
              issue: issue,
              onOpen: _openCard,
              onCta: _ctaCard,
            );
          },
        ),
      const SliverToBoxAdapter(child: SizedBox(height: 12)),
    ];
  }
}

/// Strong rule that marks the start of the NEWS block (ISSUE → NEWS only).
class _NewsSectionRule extends StatelessWidget {
  const _NewsSectionRule();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.only(top: 12),
      child: ColoredBox(
        color: TakeleyColors.hairline,
        child: SizedBox(width: double.infinity, height: 8),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({
    required this.title,
    required this.moreLabel,
    required this.onMore,
    this.topPadding = 8,
  });

  final String title;
  final String moreLabel;
  final VoidCallback onMore;
  final double topPadding;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(20, topPadding, 20, 4),
      child: Row(
        children: [
          Expanded(
            child: Text(
              title,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
            ),
          ),
          GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: onMore,
            child: Text(
              moreLabel,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: TakeleyColors.accent,
                    fontWeight: FontWeight.w600,
                  ),
            ),
          ),
        ],
      ),
    );
  }
}
