import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:share_plus/share_plus.dart';

import '../api/api_client.dart';
import '../api/columnists_api.dart';
import '../api/contributor_api.dart';
import '../api/device_session.dart';
import '../api/issues_api.dart';
import '../api/models.dart';
import '../navigation/cupertino_nav.dart';
import 'columnist_profile_screen.dart';
import '../theme/takeley_colors.dart';
import '../utils/category_label.dart';
import '../utils/contributor_ui.dart';
import '../utils/format_news_time.dart';
import '../utils/resolve_image.dart';
import '../utils/share_issue.dart';
import '../widgets/column_markdown.dart';
import '../widgets/columnist_avatar.dart';
import '../widgets/data_state.dart';
import '../widgets/deep_thought_card.dart';
import '../widgets/share_choice_sheet.dart';
import '../widgets/takeley_buttons.dart';
import 'deep_thought_detail_screen.dart';
import 'deep_thought_list_screen.dart';
import 'deep_thought_writer_screen.dart';

enum IssueDeepFocusMode { detail, writer, list }

class IssueDeepFocus {
  const IssueDeepFocus({required this.mode, this.takeId});

  final IssueDeepFocusMode mode;
  final String? takeId;
}

int _estimateReadMinutes(Issue issue) {
  final body = issue.columnBody.trim().isNotEmpty
      ? issue.columnBody
      : '${issue.summary}${issue.whyItMatters}';
  final chars = body.replaceAll(RegExp(r'\s+'), '').length;
  return chars <= 0 ? 1 : (chars / 500).round().clamp(1, 999);
}

String _sourceLabel(IssueSource s) {
  final author = (s.author ?? '').trim();
  if (author.isNotEmpty && !RegExp(r'^\d+$').hasMatch(author)) {
    return '@${author.replaceFirst(RegExp(r'^@'), '')}';
  }
  final provider = (s.provider ?? '').trim().toLowerCase();
  if (provider == 'x' || provider == 'twitter') return 'X';
  if (provider == 'news') return 'News';
  if (provider.isNotEmpty) return provider.toUpperCase();
  return '원문';
}

class IssueDetailScreen extends StatefulWidget {
  const IssueDetailScreen({
    super.key,
    required this.issueId,
    required this.issuesApi,
    required this.contributorApi,
    required this.session,
    required this.onBack,
    this.initialDeepFocus,
    this.shareId,
    this.refUserId,
  });

  final String issueId;
  final IssuesApi issuesApi;
  final ContributorApi contributorApi;
  final DeviceSession session;
  final VoidCallback onBack;
  final IssueDeepFocus? initialDeepFocus;
  final String? shareId;
  final String? refUserId;

  @override
  State<IssueDetailScreen> createState() => _IssueDetailScreenState();
}

class _IssueDetailScreenState extends State<IssueDetailScreen> {
  static final Set<String> _recordedShareOpens = <String>{};

  Issue? _issue;
  List<IssueComment> _comments = [];
  bool _loading = true;
  String? _error;
  final _commentCtrl = TextEditingController();
  bool _submitting = false;
  bool _voting = false;
  String? _pendingOptionId;
  bool _shareBusy = false;
  bool _didOpenInitialFocus = false;
  List<IssueTake> _publishedTakes = [];
  List<IssueTake> _myTakes = [];
  String? _contributorStatus;

  @override
  void initState() {
    super.initState();
    _recordSharedLinkOpened();
    _load();
  }

  void _recordSharedLinkOpened() {
    final sid = widget.shareId;
    if (sid == null || sid.isEmpty || widget.issueId.isEmpty) return;
    final key = 'share_open:${widget.issueId}:$sid';
    if (!_recordedShareOpens.add(key)) return;
    unawaited(widget.issuesApi.recordEvent(
      id: widget.issueId,
      event: 'shared_link_opened',
      userId: widget.session.userId,
      shareId: sid,
      refUserId: widget.refUserId,
    ));
  }

  @override
  void didUpdateWidget(covariant IssueDetailScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.issueId != widget.issueId ||
        oldWidget.shareId != widget.shareId) {
      _recordSharedLinkOpened();
    }
    if (oldWidget.issueId != widget.issueId) {
      setState(() {
        _didOpenInitialFocus = false;
        _pendingOptionId = null;
      });
      _load();
    }
  }

  @override
  void dispose() {
    _commentCtrl.dispose();
    super.dispose();
  }

  void _popRoute() {
    if (!mounted) return;
    Navigator.of(context).pop();
  }

  Future<void> _openColumns() async {
    final issue = _issue;
    if (issue == null || !mounted) return;
    final authorName = (issue.columnAuthorName ?? '').trim();
    final authorImage = resolveImageUrl(issue.columnAuthorImageUrl);
    final columnBody = issue.columnBody.trim();
    final updatedLabel = formatNewsTime(
      issueStoryTimestamp(
        publishedAt: issue.publishedAt,
        firstSeenAt: issue.firstSeenAt,
        contentUpdatedAt: issue.contentUpdatedAt,
      ),
    );
    final coverImage = resolveImageUrl(issue.imageUrl);
    final sources = issue.sources.take(8).toList();
    final readMin = _estimateReadMinutes(issue);

    await pushCupertinoPage(
      context,
      Scaffold(
        backgroundColor: TakeleyColors.canvas,
        body: SafeArea(
          child: Column(
            children: [
              _navBar(onBack: _popRoute),
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(20, 12, 20, 40),
                  children: [
                    const Text(
                      'COLUMN',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.7,
                        color: TakeleyColors.accent,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      issue.title,
                      style: const TextStyle(
                        fontWeight: FontWeight.w800,
                        fontSize: 26,
                        height: 1.25,
                        letterSpacing: -0.4,
                        color: TakeleyColors.fg,
                      ),
                    ),
                    if (issue.summary.trim().isNotEmpty) ...[
                      const SizedBox(height: 12),
                      Text(
                        issue.summary.trim(),
                        style: const TextStyle(
                          fontSize: 16,
                          height: 1.55,
                          fontWeight: FontWeight.w400,
                          color: Color(0xFF444444),
                          letterSpacing: -0.2,
                        ),
                      ),
                    ],
                    if (authorName.isNotEmpty)
                      _columnByline(
                        name: authorName,
                        imageUrl: authorImage,
                        updatedLabel: updatedLabel,
                        readMinutes: readMin,
                        columnistId: issue.columnistId,
                      ),
                    if (coverImage != null)
                      Padding(
                        padding: EdgeInsets.only(
                          top: authorName.isEmpty ? 16 : 0,
                          bottom: 16,
                        ),
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(12),
                          child: CachedNetworkImage(
                            imageUrl: coverImage,
                            width: double.infinity,
                            fit: BoxFit.fitWidth,
                            alignment: Alignment.topCenter,
                          ),
                        ),
                      ),
                    ColumnMarkdownView(source: columnBody),
                    _sourceCredit(sources),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _openDeepList() async {
    if (!mounted) return;
    await pushCupertinoPage(
      context,
      DeepThoughtListScreen(
        contributorApi: widget.contributorApi,
        issueId: widget.issueId,
        userId: _userId,
        initialTakes: _publishedTakes,
        canWriteDeep: showDeepThoughtWriterCta(_contributorStatus),
        onBack: _popRoute,
        onWrite: () => unawaited(_openWriter()),
      ),
    );
  }

  Future<void> _openDeepDetail(String takeId) async {
    if (!mounted) return;
    await pushCupertinoPage(
      context,
      DeepThoughtDetailScreen(
        contributorApi: widget.contributorApi,
        issueId: widget.issueId,
        takeId: takeId,
        userId: _userId,
        onBack: _popRoute,
      ),
    );
  }

  Future<void> _openWriter({String? takeId}) async {
    final issue = _issue;
    if (issue == null || !mounted) return;
    final initial = _pickWriterTake(takeId: takeId);
    await pushCupertinoPage(
      context,
      DeepThoughtWriterScreen(
        contributorApi: widget.contributorApi,
        issueId: widget.issueId,
        issueTitle: issue.title,
        issueSummary: issue.summary,
        userId: _userId,
        initialTake: initial,
        onBack: _popRoute,
        onSaved: (_) {
          unawaited(_reloadDeepThoughts());
        },
      ),
    );
    if (mounted) unawaited(_reloadDeepThoughts());
  }

  IssueTake? _pickWriterTake({String? takeId}) {
    if (takeId != null) {
      final found = _myTakes.where((t) => t.id == takeId).firstOrNull;
      if (found != null) return found;
    }
    return _myTakes
            .where((t) => t.status == 'draft' || t.status == 'rejected')
            .firstOrNull ??
        _myTakes.where((t) => t.status == 'pending_review').firstOrNull;
  }

  void _maybeOpenInitialDeepFocus() {
    if (_didOpenInitialFocus || !mounted) return;
    final focus = widget.initialDeepFocus;
    if (focus == null) return;
    _didOpenInitialFocus = true;
    switch (focus.mode) {
      case IssueDeepFocusMode.list:
        unawaited(_openDeepList());
      case IssueDeepFocusMode.detail:
        final id = focus.takeId;
        if (id != null) unawaited(_openDeepDetail(id));
      case IssueDeepFocusMode.writer:
        unawaited(_openWriter(takeId: focus.takeId));
    }
  }

  String? get _userId => widget.session.userId;

  Future<void> _reloadDeepThoughts() async {
    try {
      final takes = await widget.contributorApi.fetchIssueTakes(
        widget.issueId,
        limit: 50,
      );
      ContributorMe? me;
      try {
        me = await widget.contributorApi.fetchMe(userId: _userId);
      } catch (_) {
        me = null;
      }
      if (!mounted) return;
      final status = me?.contributorStatus ?? 'NONE';
      setState(() => _contributorStatus = status);
      setState(() => _publishedTakes = rankIssueTakes(takes));
      if (status == 'APPROVED') {
        try {
          final mine = await widget.contributorApi.fetchMyIssueTakes(
            widget.issueId,
            userId: _userId,
          );
          if (mounted) setState(() => _myTakes = mine);
        } catch (_) {
          if (mounted) setState(() => _myTakes = []);
        }
      } else {
        setState(() => _myTakes = []);
      }
    } catch (_) {
      if (mounted) setState(() => _publishedTakes = []);
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final userId = _userId;
      final issue = await widget.issuesApi.fetchIssue(
        widget.issueId,
        userId: userId,
      );
      final comments =
          await widget.issuesApi.fetchComments(widget.issueId);
      if (!mounted) return;
      setState(() {
        _issue = issue;
        _comments = comments;
        _loading = false;
      });
      unawaited(widget.issuesApi.view(widget.issueId, userId: userId));
      await _reloadDeepThoughts();
      _maybeOpenInitialDeepFocus();
      unawaited(widget.issuesApi.recordEvent(
        id: widget.issueId,
        event: 'open',
        userId: userId,
      ));
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = '이슈를 불러오지 못했어요.';
      });
    }
  }

  void _pickOption(String optionId) {
    if (_voting || _issue == null || (_issue!.myOptionId?.isNotEmpty ?? false)) {
      return;
    }
    setState(() => _pendingOptionId = optionId);
  }

  Future<void> _confirmVote() async {
    final optionId = _pendingOptionId;
    if (_voting ||
        _issue == null ||
        optionId == null ||
        optionId.isEmpty ||
        (_issue!.myOptionId?.isNotEmpty ?? false)) {
      return;
    }
    setState(() => _voting = true);
    try {
      final userId = _userId;
      final data = await widget.issuesApi.participateRaw(
        id: widget.issueId,
        optionId: optionId,
        userId: userId,
      );
      final optionsRaw = data['options'];
      final options = optionsRaw is List
          ? optionsRaw
              .whereType<Map>()
              .map((e) => IssueOption.fromJson(Map<String, dynamic>.from(e)))
              .toList()
          : _issue!.options;
      if (!mounted) return;
      setState(() {
        _pendingOptionId = null;
        _issue = _issue!.copyWith(
          myOptionId: '${data['my_option_id'] ?? optionId}',
          participationCount:
              (data['participation_count'] as num?)?.toInt() ??
                  _issue!.participationCount,
          options: options,
          isFollowing: data['is_following'] == true || _issue!.isFollowing,
        );
      });
      final picked = _votedLabel(_issue!);
      if (mounted && picked != null) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('‘$picked’를 선택했어요. 선택은 바꿀 수 없어요.')),
        );
      }
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('생각을 남기지 못했어요. 잠시 후 다시 시도해 주세요.')),
      );
    } finally {
      if (mounted) setState(() => _voting = false);
    }
  }

  Future<void> _toggleFollow() async {
    final issue = _issue;
    if (issue == null) return;
    try {
      final userId = _userId;
      final next = issue.isFollowing
          ? await widget.issuesApi.unfollow(issue.id, userId: userId)
          : await widget.issuesApi.follow(issue.id, userId: userId);
      if (!mounted) return;
      setState(() => _issue = next);
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('관심 설정을 바꾸지 못했어요.')),
      );
    }
  }

  Future<void> _share() async {
    final issue = _issue;
    if (issue == null || _shareBusy) return;
    final votedLabel = _votedLabel(issue);
    var includeTake = false;
    if (votedLabel != null) {
      final choice = await showShareChoiceSheet(
        context,
        takeLabel: votedLabel,
      );
      if (choice == null || !mounted) return;
      includeTake = choice;
    }
    await _sendShare(includeTake: includeTake, takeLabel: votedLabel);
  }

  String? _votedLabel(Issue issue) {
    final id = issue.myOptionId;
    if (id == null || id.isEmpty) return null;
    for (final opt in issue.options) {
      if (opt.id == id) return opt.label;
    }
    return null;
  }

  Future<void> _sendShare({
    required bool includeTake,
    String? takeLabel,
  }) async {
    final issue = _issue;
    if (issue == null || _shareBusy) return;
    setState(() => _shareBusy = true);
    final payload = buildSharePayload(
      id: issue.id,
      title: issue.title,
      participationSuitable: issue.participationSuitable,
      trendStatus: issue.trendStatus,
      isTrending: issue.isTrending,
      refUserId: _userId,
      includeTake: includeTake,
      takeLabel: takeLabel,
    );
    final intent = shareIntentName(payload.intent);
    unawaited(widget.issuesApi.recordEvent(
      id: widget.issueId,
      event: 'share_clicked',
      userId: _userId,
      shareId: payload.shareId,
      refUserId: _userId,
      shareIntent: intent,
    ));
    try {
      final result = await SharePlus.instance.share(
        payload.shareAsUri
            ? ShareParams(
                uri: Uri.parse(payload.url),
                subject: payload.title,
                title: payload.title,
              )
            : ShareParams(
                text: payload.text,
                subject: payload.title,
                title: payload.title,
              ),
      );
      // unavailable means the platform could not say whether anything was sent.
      final event = switch (result.status) {
        ShareResultStatus.success => 'share_completed',
        ShareResultStatus.dismissed => 'share_cancelled',
        ShareResultStatus.unavailable => null,
      };
      if (event != null) {
        unawaited(widget.issuesApi.recordEvent(
          id: widget.issueId,
          event: event,
          userId: _userId,
          shareId: payload.shareId,
          refUserId: _userId,
          shareIntent: intent,
        ));
      }
    } catch (_) {
      /* share sheet failed — click already recorded */
    } finally {
      if (mounted) setState(() => _shareBusy = false);
    }
  }

  Future<void> _submitComment() async {
    final text = _commentCtrl.text.trim();
    if (text.isEmpty || _submitting) return;
    setState(() => _submitting = true);
    try {
      final comment = await widget.issuesApi.postComment(
        id: widget.issueId,
        content: text,
        userId: _userId,
      );
      if (!mounted) return;
      setState(() {
        _comments = [comment, ..._comments];
        _commentCtrl.clear();
        if (_issue != null) {
          _issue = _issue!.copyWith(commentCount: _issue!.commentCount + 1);
        }
      });
      FocusManager.instance.primaryFocus?.unfocus();
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('댓글을 남기지 못했어요.')),
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Widget _navBar({
    required VoidCallback onBack,
    bool showActions = false,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.fromLTRB(4, 4, 12, 4),
      decoration: const BoxDecoration(
        color: Color(0xF2FFFFFF),
        border: Border(
          bottom: BorderSide(color: TakeleyColors.border, width: 1),
        ),
      ),
      child: Row(
        children: [
          IconButton(
            onPressed: onBack,
            icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18),
            tooltip: '뒤로',
          ),
          const Spacer(),
          if (showActions && _issue != null) ...[
            IconButton(
              onPressed: _toggleFollow,
              icon: Icon(
                _issue!.isFollowing
                    ? Icons.bookmark
                    : Icons.bookmark_outline,
                size: 22,
                color: _issue!.isFollowing
                    ? TakeleyColors.accent
                    : TakeleyColors.fg,
              ),
              tooltip: _issue!.isFollowing ? '팔로우 해제' : '이슈 팔로우',
            ),
            IconButton(
              onPressed: _shareBusy ? null : _share,
              icon: const Icon(Icons.ios_share_rounded, size: 22),
              tooltip: '공유',
            ),
          ],
        ],
      ),
    );
  }

  Widget _sourceCredit(List<IssueSource> sources) {
    if (sources.isEmpty) return const SizedBox.shrink();
    final credits = <({String key, String label, String? url})>[];
    final seen = <String>{};
    for (final s in sources) {
      final label = _sourceLabel(s);
      final key = label.toLowerCase();
      if (seen.contains(key)) continue;
      seen.add(key);
      credits.add((key: key, label: label, url: s.url));
    }
    return Padding(
      padding: const EdgeInsets.only(top: 28),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.only(top: 18),
        decoration: const BoxDecoration(
          border: Border(
            top: BorderSide(color: TakeleyColors.border, width: 1),
          ),
        ),
        child: Wrap(
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            const Text(
              '출처 ',
              style: TextStyle(
                fontWeight: FontWeight.w700,
                fontSize: 13,
                letterSpacing: 0.4,
                color: TakeleyColors.muted,
              ),
            ),
            for (var i = 0; i < credits.length; i++) ...[
              if (i > 0)
                const Text(
                  ' · ',
                  style: TextStyle(color: TakeleyColors.muted),
                ),
              Text(
                credits[i].label,
                style: const TextStyle(
                  color: TakeleyColors.accent,
                  fontWeight: FontWeight.w600,
                  fontSize: 13,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  void _openColumnist(String columnistId) {
    unawaited(
      pushCupertinoPage(
        context,
        ColumnistProfileScreen(
          columnistId: columnistId,
          columnistsApi: ColumnistsApi(ApiClient()),
          onIssueOpen: (issueId) {
            unawaited(
              pushCupertinoPage(
                context,
                IssueDetailScreen(
                  issueId: issueId,
                  issuesApi: widget.issuesApi,
                  contributorApi: widget.contributorApi,
                  session: widget.session,
                  onBack: () => Navigator.of(context).pop(),
                ),
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _columnByline({
    required String name,
    required String? imageUrl,
    required String? updatedLabel,
    int? readMinutes,
    String? columnistId,
  }) {
    final initial =
        name.trim().isNotEmpty ? String.fromCharCodes(name.runes.take(1)) : '?';
    final meta = <String>[];
    if (updatedLabel != null && updatedLabel.isNotEmpty) {
      meta.add('$updatedLabel 업데이트');
    }
    if (readMinutes != null && readMinutes > 0) {
      meta.add('$readMinutes분 읽기');
    }
    final canOpen = columnistId != null && columnistId.trim().isNotEmpty;
    return Padding(
      padding: const EdgeInsets.only(top: 16, bottom: 16),
      child: InkWell(
        onTap: canOpen ? () => _openColumnist(columnistId.trim()) : null,
        child: Row(
        children: [
          ColumnistAvatar(size: 40, imageUrl: imageUrl, initial: initial),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  name,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    color: TakeleyColors.fg,
                  ),
                ),
                Text(
                  meta.join(' · '),
                  style: const TextStyle(
                    color: Color(0xFF444444),
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
        ],
        ),
      ),
    );
  }

  Widget _columnCta({required VoidCallback onTap, String? hint}) {
    return Padding(
      padding: const EdgeInsets.only(top: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TakeleyOffsetPillButton(
            label: '컬럼 자세히 보기',
            onPressed: onTap,
          ),
          if (hint != null) ...[
            const SizedBox(height: 8),
            Text(
              hint,
              textAlign: TextAlign.center,
              style: const TextStyle(color: TakeleyColors.muted, fontSize: 13),
            ),
          ],
        ],
      ),
    );
  }

  Widget _deepThoughtCta({required VoidCallback onTap}) {
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: TakeleyOffsetPillButton(
        label: '생각 더 깊게 남기기',
        onPressed: onTap,
      ),
    );
  }

  Widget _votePanel(Issue issue) {
    final canVote = issue.participationSuitable &&
        (issue.participationQuestion?.isNotEmpty ?? false);
    if (!canVote) return const SizedBox.shrink();
    final hasTake = issue.myOptionId != null && issue.myOptionId!.isNotEmpty;
    final totalVotes = issue.participationCount;
    final fmt = NumberFormat.decimalPattern('ko_KR');
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(top: 28),
      padding: const EdgeInsets.fromLTRB(16, 18, 16, 16),
      decoration: BoxDecoration(
        color: TakeleyColors.soft,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '당신의 생각은?',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.5,
              color: TakeleyColors.accent,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            issue.participationQuestion!,
            style: const TextStyle(
              fontWeight: FontWeight.w600,
              fontSize: 16,
              height: 1.35,
            ),
          ),
          const SizedBox(height: 12),
          ...issue.options.map((opt) {
            final selected = hasTake
                ? issue.myOptionId == opt.id
                : _pendingOptionId == opt.id;
            final pct =
                totalVotes > 0 ? ((opt.count / totalVotes) * 100).round() : 0;
            final meta = hasTake && totalVotes > 0
                ? '$pct% · ${fmt.format(opt.count)}'
                : '';
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: TakeleyVoteOptionButton(
                label: opt.label,
                meta: meta,
                selected: selected,
                enabled: !_voting,
                onPressed: hasTake ? null : () => _pickOption(opt.id),
              ),
            );
          }),
          if (!hasTake && _pendingOptionId != null) ...[
            const SizedBox(height: 4),
            TakeleyOffsetPillButton(
              label: _voting ? '결과 여는 중…' : '결과 보기',
              enabled: !_voting,
              onPressed: _confirmVote,
            ),
            const SizedBox(height: 10),
          ],
          Text(
            hasTake
                ? '${fmt.format(issue.participationCount)}명 생각 남김'
                : _pendingOptionId == null
                    ? '선택한 뒤에 다른 사람 생각을 볼 수 있어요.'
                    : '다른 선택지를 누르면 바꿀 수 있어요.',
            style: const TextStyle(color: TakeleyColors.muted, fontSize: 13),
          ),
        ],
      ),
    );
  }

  Widget _deepThoughtSection(bool canWriteDeep) {
    final showSection = _publishedTakes.isNotEmpty || canWriteDeep;
    if (!showSection) return const SizedBox.shrink();
    final ranked = _publishedTakes;
    final preview = ranked.take(kDeepThoughtPreviewLimit).toList();
    final remaining = ranked.length - preview.length;

    return Padding(
      padding: const EdgeInsets.only(top: 32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '깊이 있는 생각',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
          ),
          if (ranked.isEmpty && canWriteDeep) ...[
            const SizedBox(height: 8),
            const Text(
              '당신의 생각을 더 깊게 남겨보세요.',
              style: TextStyle(color: TakeleyColors.muted, height: 1.45),
            ),
            _deepThoughtCta(
              onTap: () => unawaited(_openWriter()),
            ),
          ],
          if (preview.isNotEmpty) ...[
            const SizedBox(height: 12),
            for (final t in preview)
              DeepThoughtCard(
                take: t,
                onTap: () => unawaited(_openDeepDetail(t.id)),
              ),
            if (remaining > 0)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: TextButton(
                  onPressed: () => unawaited(_openDeepList()),
                  style: TextButton.styleFrom(
                    foregroundColor: TakeleyColors.accent,
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    minimumSize: Size.zero,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                  child: Text(
                    '생각 $remaining개 더 보기',
                    style: const TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ),
          ],
          if (ranked.isNotEmpty && canWriteDeep)
            _deepThoughtCta(
              onTap: () => unawaited(_openWriter()),
            ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: TakeleyColors.canvas,
      body: SafeArea(
        child: Column(
          children: [
            _navBar(onBack: widget.onBack, showActions: !_loading),
            Expanded(child: _buildMainBody(context)),
          ],
        ),
      ),
    );
  }

  Widget _buildMainBody(BuildContext context) {
    if (_loading) {
      return const Center(
        child: CircularProgressIndicator(color: TakeleyColors.accent),
      );
    }
    if (_error != null || _issue == null) {
      return DataState(
        message: _error ?? '이슈를 찾을 수 없어요.',
        actionLabel: '다시 시도',
        onAction: _load,
      );
    }

    final issue = _issue!;
    final imageUrl = resolveImageUrl(issue.imageUrl);
    final metaParts = <String>[];
    if (issue.sourceCount > 0) metaParts.add('출처 ${issue.sourceCount}');
    final sources = issue.sources.take(8).toList();
    final canWriteDeep = showDeepThoughtWriterCta(_contributorStatus);
    final hasColumn = issue.columnBody.trim().isNotEmpty;

    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 4, 20, 40),
      children: [
        Text(
          categoryLabel(issue.category),
          style: Theme.of(context).textTheme.labelLarge,
        ),
        const SizedBox(height: 8),
        Text(
          issue.title,
          style: Theme.of(context).textTheme.headlineLarge,
        ),
        if (issue.summary.isNotEmpty) ...[
          const SizedBox(height: 12),
          Text(
            issue.summary,
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                  height: 1.55,
                  color: TakeleyColors.muted,
                ),
          ),
        ],
        if ((issue.columnAuthorName ?? '').trim().isNotEmpty)
          _columnByline(
            name: issue.columnAuthorName!.trim(),
            imageUrl: resolveImageUrl(issue.columnAuthorImageUrl),
            updatedLabel: formatNewsTime(
              issueStoryTimestamp(
                publishedAt: issue.publishedAt,
                firstSeenAt: issue.firstSeenAt,
                contentUpdatedAt: issue.contentUpdatedAt,
              ),
            ),
            readMinutes: _estimateReadMinutes(issue),
            columnistId: issue.columnistId,
          ),
        if (imageUrl != null) ...[
          const SizedBox(height: 16),
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: CachedNetworkImage(
              imageUrl: imageUrl,
              width: double.infinity,
              fit: BoxFit.fitWidth,
              alignment: Alignment.topCenter,
            ),
          ),
        ],
        if (metaParts.isNotEmpty) ...[
          const SizedBox(height: 12),
          Text(
            metaParts.join(' · '),
            style: const TextStyle(color: TakeleyColors.muted, fontSize: 13),
          ),
        ],
        if (issue.whyItMatters.trim().isNotEmpty) ...[
          const SizedBox(height: 28),
          Text(
            '왜 중요한가',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
          ),
          const SizedBox(height: 8),
          Text(issue.whyItMatters, style: const TextStyle(height: 1.55)),
        ],
        if (issue.keyPoints.isNotEmpty) ...[
          const SizedBox(height: 28),
          Text(
            '핵심만 보면',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
          ),
          const SizedBox(height: 8),
          ...issue.keyPoints.map(
            (p) => Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('• '),
                  Expanded(child: Text(p, style: const TextStyle(height: 1.45))),
                ],
              ),
            ),
          ),
        ],
        if (hasColumn)
          _columnCta(
            onTap: _openColumns,
            hint: '이 이슈를 긴 글로 읽어 보세요',
          ),
        _votePanel(issue),
        _deepThoughtSection(canWriteDeep),
        _sourceCredit(sources),
        const SizedBox(height: 32),
        Text(
          '댓글 · ${issue.commentCount}',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w700,
              ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _commentCtrl,
          maxLines: 3,
          minLines: 3,
          onChanged: (_) => setState(() {}),
          onTapOutside: (_) => FocusManager.instance.primaryFocus?.unfocus(),
          decoration: const InputDecoration(
            hintText: '짧은 생각을 남겨 보세요',
          ),
        ),
        const SizedBox(height: 10),
        Align(
          alignment: Alignment.centerRight,
          child: TakeleyOffsetPillButton(
            label: '등록',
            fullWidth: false,
            minHeight: 44,
            fontSize: 15,
            shadowOffset: 3,
            enabled: !_submitting && _commentCtrl.text.trim().isNotEmpty,
            onPressed: _submitComment,
          ),
        ),
        const SizedBox(height: 14),
        if (_comments.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 14),
            child: Text(
              '아직 댓글이 없어요',
              style: TextStyle(color: TakeleyColors.muted, fontSize: 15),
            ),
          )
        else
          ..._comments.map((c) {
            final name = (c.displayName ?? '').trim();
            return Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 14.4),
              decoration: const BoxDecoration(
                border: Border(
                  bottom: BorderSide(color: TakeleyColors.border, width: 1),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    name.isEmpty ? '익명' : name,
                    style: const TextStyle(
                      fontWeight: FontWeight.w600,
                      fontSize: 13,
                      color: TakeleyColors.muted,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    c.content,
                    style: const TextStyle(
                      fontSize: 15,
                      height: 1.5,
                      color: TakeleyColors.fg,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    formatNewsTime(c.createdAt),
                    style: const TextStyle(
                      color: TakeleyColors.muted,
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            );
          }),
      ],
    );
  }
}
