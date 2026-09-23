import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../api/device_session.dart';
import '../api/issues_api.dart';
import '../api/models.dart';
import '../screens/issue_detail_screen.dart';
import '../theme/takeley_colors.dart';
import '../utils/contributor_ui.dart';
import '../utils/format_news_time.dart';
import '../utils/tab_visibility_reload.dart';
import '../widgets/data_state.dart';
import '../widgets/issue_card.dart';
import '../widgets/profile_chrome.dart';

/// Mirrors `frontend/src/screens/ActivityScreen.tsx`.
class ActivityScreen extends StatefulWidget {
  const ActivityScreen({
    super.key,
    required this.issuesApi,
    required this.session,
    required this.onIssueOpen,
    this.onDeepThoughtOpen,
  });

  final IssuesApi issuesApi;
  final DeviceSession session;
  final ValueChanged<String> onIssueOpen;
  final void Function(String issueId, IssueDeepFocus focus)? onDeepThoughtOpen;

  @override
  State<ActivityScreen> createState() => _ActivityScreenState();
}

class _ActivityScreenState extends State<ActivityScreen>
    with TabVisibilityReloadMixin {
  String _tab = 'votes';
  List<Issue> _votes = [];
  List<Issue> _followed = [];
  List<IssueComment> _comments = [];
  ContributorStats? _contributorStats;
  List<MyDeepThought> _deepThoughts = [];
  bool _loading = true;
  String? _error;

  @override
  String get tabPath => '/activity';

  @override
  void onTabBecameVisible() => _load(silent: true);

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load({bool silent = false}) async {
    if (!silent) {
      setState(() {
        _loading = true;
        _error = null;
      });
    } else {
      setState(() => _error = null);
    }
    try {
      final data = await widget.issuesApi.fetchMyActivity(
        userId: widget.session.userId,
      );
      if (!mounted) return;
      setState(() {
        _votes = data.participations;
        _followed = data.followed;
        _comments = data.comments;
        _contributorStats = data.contributorStats;
        _deepThoughts = data.myDeepThoughts;
        _loading = false;
        if (_contributorStats == null && _tab == 'writes') {
          _tab = 'votes';
        }
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = '내 이슈를 불러오지 못했어요.';
      });
    }
  }

  bool get _showContributor => _contributorStats != null;

  void _openDeepThought(MyDeepThought item) {
    final mode = deepFocusForMyTake(item.status);
    final focus = IssueDeepFocus(
      mode: mode == 'detail'
          ? IssueDeepFocusMode.detail
          : IssueDeepFocusMode.writer,
      takeId: item.id,
    );
    if (widget.onDeepThoughtOpen != null) {
      widget.onDeepThoughtOpen!(item.issueId, focus);
    } else {
      widget.onIssueOpen(item.issueId);
    }
  }

  @override
  Widget build(BuildContext context) {
    final tabs = <({String id, String label})>[
      (id: 'votes', label: '참여'),
      (id: 'followed', label: '팔로우'),
      (id: 'comments', label: '댓글'),
      if (_showContributor) (id: 'writes', label: '생각'),
    ];

    final emptyAll = !_loading &&
        _error == null &&
        _votes.isEmpty &&
        _followed.isEmpty &&
        _comments.isEmpty &&
        !_showContributor;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const ScreenTopBar(
          title: '내 이슈',
        ),
        if (_loading)
          const Expanded(
            child: Center(
              child: CircularProgressIndicator(color: TakeleyColors.accent),
            ),
          )
        else if (_error != null)
          Expanded(
            child: DataState(
              message: _error!,
              actionLabel: '다시 시도',
              onAction: _load,
            ),
          )
        else if (emptyAll)
          const Expanded(
            child: DataState(
              message: '아직 관심 이슈가 없어요.\n홈에서 이슈를 읽고 생각을 남기거나 팔로우해 보세요.',
            ),
          )
        else ...[
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 12),
            child: Row(
              children: tabs.map((t) {
                final active = _tab == t.id;
                return Expanded(
                  child: Padding(
                    padding: const EdgeInsets.only(right: 6),
                    child: GestureDetector(
                      onTap: () => setState(() => _tab = t.id),
                      child: Container(
                        padding: const EdgeInsets.symmetric(vertical: 10),
                        decoration: BoxDecoration(
                          color: active
                              ? TakeleyColors.accentSoft
                              : TakeleyColors.soft,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Text(
                          t.label,
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            fontWeight: FontWeight.w600,
                            fontSize: 13,
                            color: active
                                ? TakeleyColors.accent
                                : TakeleyColors.fg,
                          ),
                        ),
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
          ),
          Expanded(child: _buildPanel()),
        ],
      ],
    );
  }

  Widget _buildPanel() {
    switch (_tab) {
      case 'followed':
        return _followCardList();
      case 'comments':
        return _commentList();
      case 'writes':
        return _writesList();
      case 'votes':
      default:
        return _votesCardList();
    }
  }

  Widget _votesCardList() {
    if (_votes.isEmpty) {
      return const DataState(message: '아직 참여한 이슈가 없어요.');
    }
    return RefreshIndicator(
      color: TakeleyColors.accent,
      onRefresh: () => _load(silent: true),
      child: ListView.separated(
        padding: const EdgeInsets.only(bottom: 88),
        itemCount: _votes.length,
        separatorBuilder: (_, __) => const Padding(
          padding: EdgeInsets.symmetric(horizontal: 20),
          child: Divider(height: 1, thickness: 2),
        ),
        itemBuilder: (context, index) {
          final issue = _votes[index];
          String? voteLabel;
          if (issue.myOptionId != null) {
            voteLabel = issue.options
                .where((o) => o.id == issue.myOptionId)
                .map((o) => o.label)
                .firstOrNull;
          }
          return IssueCard(
            issue: issue,
            imageLayout: IssueCardImageLayout.trailing,
            takeLabel: voteLabel,
            showSummary: false,
            ctaLabel: '다시 보기 →',
            onOpen: (i) => widget.onIssueOpen(i.id),
          );
        },
      ),
    );
  }

  Widget _followCardList() {
    if (_followed.isEmpty) {
      return const DataState(message: '팔로우한 이슈가 없어요.');
    }
    return RefreshIndicator(
      color: TakeleyColors.accent,
      onRefresh: () => _load(silent: true),
      child: ListView.separated(
        padding: const EdgeInsets.only(bottom: 88),
        itemCount: _followed.length,
        separatorBuilder: (_, __) => const Padding(
          padding: EdgeInsets.symmetric(horizontal: 20),
          child: Divider(height: 1, thickness: 2),
        ),
        itemBuilder: (context, index) {
          final issue = _followed[index];
          return IssueCard(
            issue: issue,
            imageLayout: IssueCardImageLayout.trailing,
            onOpen: (i) => widget.onIssueOpen(i.id),
          );
        },
      ),
    );
  }

  Widget _commentList() {
    if (_comments.isEmpty) {
      return const DataState(message: '남긴 댓글이 없어요.');
    }
    return RefreshIndicator(
      color: TakeleyColors.accent,
      onRefresh: () => _load(silent: true),
      child: ListView.separated(
        padding: const EdgeInsets.only(bottom: 88),
        itemCount: _comments.length,
        separatorBuilder: (_, __) => const Padding(
          padding: EdgeInsets.symmetric(horizontal: 20),
          child: Divider(height: 1, thickness: 1),
        ),
        itemBuilder: (context, index) {
          final c = _comments[index];
          final issueLabel =
              c.issueTitle.trim().isEmpty ? '이슈' : c.issueTitle.trim();
          final when = formatNewsTime(c.createdAt);
          return _ActivityTapRow(
            onTap: () => widget.onIssueOpen(c.issueId),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  issueLabel,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: TakeleyColors.secondaryLabel,
                    letterSpacing: -0.2,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  c.content,
                  maxLines: 4,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    height: 1.4,
                    letterSpacing: -0.3,
                    color: TakeleyColors.fg,
                  ),
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        when.isEmpty ? '댓글' : when,
                        style: const TextStyle(
                          fontSize: 13,
                          color: TakeleyColors.muted,
                        ),
                      ),
                    ),
                    const Text(
                      '이슈 보기 →',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: TakeleyColors.accent,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _writesList() {
    if (_deepThoughts.isEmpty) {
      return const DataState(message: '아직 남긴 생각이 없어요.');
    }
    final fmt = NumberFormat.decimalPattern('ko_KR');
    return RefreshIndicator(
      color: TakeleyColors.accent,
      onRefresh: () => _load(silent: true),
      child: ListView.separated(
        padding: const EdgeInsets.only(bottom: 88),
        itemCount: _deepThoughts.length,
        separatorBuilder: (_, __) => const Padding(
          padding: EdgeInsets.symmetric(horizontal: 20),
          child: Divider(height: 1, thickness: 1),
        ),
        itemBuilder: (context, index) {
          final t = _deepThoughts[index];
          final issueLabel =
              t.issueTitle.trim().isEmpty ? '이슈' : t.issueTitle.trim();
          return _ActivityTapRow(
            onTap: () => _openDeepThought(t),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  issueLabel,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: TakeleyColors.secondaryLabel,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  t.title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w700,
                    height: 1.35,
                    letterSpacing: -0.3,
                    color: TakeleyColors.fg,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  '${takeStatusLabel(t.status)} · 조회 ${fmt.format(t.viewCount)} · 공감 ${fmt.format(t.reactionCount)}',
                  style: const TextStyle(
                    fontSize: 13,
                    color: TakeleyColors.muted,
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _ActivityTapRow extends StatefulWidget {
  const _ActivityTapRow({required this.onTap, required this.child});

  final VoidCallback onTap;
  final Widget child;

  @override
  State<_ActivityTapRow> createState() => _ActivityTapRowState();
}

class _ActivityTapRowState extends State<_ActivityTapRow> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) => setState(() => _pressed = false),
      onTapCancel: () => setState(() => _pressed = false),
      onTap: widget.onTap,
      child: AnimatedOpacity(
        duration: const Duration(milliseconds: 100),
        opacity: _pressed ? 0.72 : 1,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 18, 20, 18),
          child: widget.child,
        ),
      ),
    );
  }
}
