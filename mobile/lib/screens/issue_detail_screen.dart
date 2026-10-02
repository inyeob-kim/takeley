import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:share_plus/share_plus.dart';

import '../api/api_client.dart';
import '../api/columnists_api.dart';
import '../api/contributor_api.dart';
import '../api/device_session.dart';
import '../api/issues_api.dart';
import '../api/models.dart';
import '../api/safety_api.dart';
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
import '../widgets/judgment_note_sheet.dart';
import '../widgets/profile_chrome.dart';
import '../widgets/takeley_buttons.dart';
import '../widgets/ugc_actions.dart';
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
  final provider = (s.provider ?? '').trim().toLowerCase();
  final author = (s.author ?? '').trim();
  final isSocial =
      provider == 'x' || provider == 'twitter' || provider == 'reddit';

  // X/Reddit: keep @handle style.
  if (isSocial &&
      author.isNotEmpty &&
      !RegExp(r'^\d+$').hasMatch(author)) {
    return '@${author.replaceFirst(RegExp(r'^@'), '')}';
  }

  final junk = {'rss', 'news', 'news-demo', 'rss_feed'};
  if (author.isNotEmpty &&
      !junk.contains(author.toLowerCase()) &&
      !RegExp(r'^\d+$').hasMatch(author)) {
    return author;
  }

  final host = _publisherFromUrl(s.url);
  if (host != null) return host;

  if (provider == 'x' || provider == 'twitter') return 'X';
  if (provider == 'news') return 'News';
  if (provider.isNotEmpty) return provider.toUpperCase();
  return '원문';
}

String? _publisherFromUrl(String? raw) {
  final t = (raw ?? '').trim();
  if (t.isEmpty) return null;
  final u = Uri.tryParse(t);
  if (u == null || u.host.isEmpty) return null;
  var host = u.host.toLowerCase();
  if (host.startsWith('www.')) host = host.substring(4);
  if (host.contains('news.google.')) return null;
  const known = <String, String>{
    'bbc.co.uk': 'BBC',
    'bbc.com': 'BBC',
    'reuters.com': 'Reuters',
    'bloomberg.com': 'Bloomberg',
    'wsj.com': 'WSJ',
    'ft.com': 'FT',
    'cnbc.com': 'CNBC',
    'nytimes.com': 'NYT',
    'theguardian.com': 'Guardian',
    'apnews.com': 'AP',
    'finance.yahoo.com': 'Yahoo Finance',
    'yahoo.com': 'Yahoo',
    'techcrunch.com': 'TechCrunch',
    'theverge.com': 'The Verge',
    'cnn.com': 'CNN',
  };
  for (final e in known.entries) {
    if (host == e.key || host.endsWith('.${e.key}')) return e.value;
  }
  final parts = host.split('.').where((p) => p.isNotEmpty).toList();
  if (parts.length >= 3 && parts[parts.length - 2] == 'co') {
    return _titleCase(parts[parts.length - 3]);
  }
  if (parts.length >= 2) return _titleCase(parts[parts.length - 2]);
  return host;
}

String _titleCase(String s) {
  if (s.isEmpty) return s;
  return s[0].toUpperCase() + s.substring(1);
}

class IssueDetailScreen extends StatefulWidget {
  const IssueDetailScreen({
    super.key,
    required this.issueId,
    required this.issuesApi,
    required this.contributorApi,
    required this.safetyApi,
    required this.session,
    required this.onBack,
    this.initialDeepFocus,
    this.shareId,
    this.refUserId,
    this.scrollToTake = false,
    this.openSource,
  });

  final String issueId;
  final IssuesApi issuesApi;
  final ContributorApi contributorApi;
  final SafetyApi safetyApi;
  final DeviceSession session;
  final VoidCallback onBack;
  final IssueDeepFocus? initialDeepFocus;
  final String? shareId;
  final String? refUserId;
  final bool scrollToTake;
  final String? openSource;

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
  bool _savingNote = false;
  Map<String, dynamic>? _otherTake;
  bool _didOpenInitialFocus = false;
  bool _didRecordTakePanel = false;
  bool _didScrollToTake = false;
  bool _didRecordDistribution = false;
  final _scroll = ScrollController();
  final _takePanelKey = GlobalKey();
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
        _didRecordTakePanel = false;
        _didScrollToTake = false;
      });
      _load();
    }
  }

  @override
  void dispose() {
    _commentCtrl.dispose();
    _scroll.dispose();
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
    _recordFunnel('column_open');

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
        safetyApi: widget.safetyApi,
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
        safetyApi: widget.safetyApi,
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
        userId: _userId,
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
      final comments = await widget.issuesApi.fetchComments(
        widget.issueId,
        userId: userId,
      );
      if (!mounted) return;
      setState(() {
        _issue = issue;
        _comments = comments;
        _loading = false;
      });
      // GET /issues/:id does not record a view. POST /view is the single open path.
      unawaited(widget.issuesApi.view(widget.issueId, userId: userId));
      await _reloadDeepThoughts();
      _maybeOpenInitialDeepFocus();
      _scheduleTakePanelFocus();
      if (issue.myOptionId != null && issue.myOptionId!.isNotEmpty) {
        unawaited(_loadOtherTake());
        _maybeRecordDistributionViewed();
      }
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = '이슈를 불러오지 못했어요.';
      });
    }
  }

  void _recordFunnel(String event) {
    if (event == 'take_panel_seen') {
      if (_didRecordTakePanel) return;
      _didRecordTakePanel = true;
    }
    final userId = _userId;
    if (userId == null || userId.isEmpty) return;
    unawaited(widget.issuesApi.recordEvent(
      id: widget.issueId,
      event: event,
      userId: userId,
      shareIntent: widget.openSource,
    ));
  }

  bool _canVote(Issue issue) {
    return issue.participationSuitable &&
        (issue.participationQuestion?.isNotEmpty ?? false);
  }

  void _scheduleTakePanelFocus() {
    final issue = _issue;
    if (issue == null) return;
    if (_canVote(issue)) {
      _recordFunnel('take_panel_seen');
    }
    if (!widget.scrollToTake || !_canVote(issue) || _didScrollToTake) return;
    _didScrollToTake = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Future<void>.delayed(const Duration(milliseconds: 120), () {
        if (!mounted) return;
        final ctx = _takePanelKey.currentContext;
        if (ctx == null || !ctx.mounted) return;
        Scrollable.ensureVisible(
          ctx,
          duration: const Duration(milliseconds: 280),
          curve: Curves.easeOutCubic,
          alignment: 0.08,
        );
      });
    });
  }

  void _pickOption(String optionId) {
    if (_voting || _issue == null) return;
    final current = _issue!.myOptionId;
    if (current != null && current.isNotEmpty && current == optionId) {
      return;
    }
    setState(() => _pendingOptionId = optionId);
    _recordFunnel('take_option_pending');
  }

  Future<void> _confirmVote() async {
    final optionId = _pendingOptionId;
    if (_voting || _issue == null || optionId == null || optionId.isEmpty) {
      return;
    }
    setState(() => _voting = true);
    _recordFunnel('take_confirm_tapped');
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
          myNote: data['my_note'] as String? ?? _issue!.myNote,
          distributionVisible: data['distribution_visible'] == true,
          participationCount:
              (data['participation_count'] as num?)?.toInt() ??
                  _issue!.participationCount,
          options: options,
          isFollowing: data['is_following'] == true || _issue!.isFollowing,
        );
      });
      final picked = _votedLabel(_issue!);
      final changed = data['position_changed'] == true;
      if (mounted && picked != null) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              changed ? '‘$picked’(으)로 입장을 바꿨어요.' : '‘$picked’를 선택했어요.',
            ),
          ),
        );
      }
      unawaited(_loadOtherTake());
      _maybeRecordDistributionViewed();
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('생각을 남기지 못했어요. 잠시 후 다시 시도해 주세요.')),
      );
    } finally {
      if (mounted) setState(() => _voting = false);
    }
  }

  void _maybeRecordDistributionViewed() {
    final issue = _issue;
    if (issue == null || _didRecordDistribution) return;
    final hasTake = issue.myOptionId != null && issue.myOptionId!.isNotEmpty;
    if (!hasTake || !issue.distributionVisible) return;
    _didRecordDistribution = true;
    unawaited(widget.issuesApi.recordEvent(
      id: widget.issueId,
      event: 'distribution_viewed',
      userId: _userId,
    ));
  }

  Future<void> _loadOtherTake() async {
    try {
      final card = await widget.issuesApi.fetchOtherTake(
        id: widget.issueId,
        userId: _userId,
      );
      if (!mounted) return;
      setState(() => _otherTake = card);
    } catch (_) {
      // Optional enrichment — ignore failures.
    }
  }

  Future<void> _openJudgmentNoteSheet() async {
    final issue = _issue;
    if (issue == null || _savingNote) return;
    _recordFunnel('take_started');
    final text = await showJudgmentNoteSheet(
      context,
      initialNote: issue.myNote,
    );
    if (!mounted || text == null || text.trim().isEmpty) return;
    await _saveNote(text.trim());
  }

  Future<void> _saveNote(String note) async {
    final issue = _issue;
    final optionId = issue?.myOptionId;
    if (issue == null || optionId == null || optionId.isEmpty || _savingNote) {
      return;
    }
    setState(() => _savingNote = true);
    try {
      final data = await widget.issuesApi.participateRaw(
        id: widget.issueId,
        optionId: optionId,
        userId: _userId,
        note: note,
      );
      if (!mounted) return;
      setState(() {
        _issue = issue.copyWith(
          myNote: data['my_note'] as String? ?? note,
          distributionVisible: data['distribution_visible'] == true,
          options: data['options'] is List
              ? (data['options'] as List)
                  .whereType<Map>()
                  .map(
                    (e) => IssueOption.fromJson(Map<String, dynamic>.from(e)),
                  )
                  .toList()
              : issue.options,
          participationCount:
              (data['participation_count'] as num?)?.toInt() ??
                  issue.participationCount,
        );
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('남겼어요. 나중에 내 판단으로 남아 있어요.')),
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('남기지 못했어요. 잠시 후 다시 해 주세요.')),
      );
    } finally {
      if (mounted) setState(() => _savingNote = false);
    }
  }

  Future<void> _skipOtherTake() async {
    final card = _otherTake;
    if (card == null) return;
    try {
      await widget.issuesApi.skipOtherTake(
        id: widget.issueId,
        userId: _userId,
        exposureId: '${card['exposure_id'] ?? ''}',
      );
    } catch (_) {}
    if (mounted) setState(() => _otherTake = null);
  }

  Future<void> _openOtherTake() async {
    final card = _otherTake;
    if (card == null) return;
    try {
      await widget.issuesApi.openOtherTake(
        id: widget.issueId,
        userId: _userId,
        exposureId: '${card['exposure_id'] ?? ''}',
      );
    } catch (_) {}
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('다른 사람의 한 줄을 확인했어요.')),
    );
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
      // share_plus throws if text and uri are both set. iOS/Android native
      // sheets take hook text and /i/{id} as separate items.
      final event =
          defaultTargetPlatform == TargetPlatform.iOS ||
                  defaultTargetPlatform == TargetPlatform.android
              ? await _sendNativeShare(payload)
              : await _sendSharePlus(payload);
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
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('지금은 공유할 수 없어요.')),
        );
      }
    } finally {
      if (mounted) setState(() => _shareBusy = false);
    }
  }

  Future<String?> _sendNativeShare(SharePayload payload) async {
    final raw = await const MethodChannel('takeley/share').invokeMethod<String>(
      'share',
      {
        'text': payload.text,
        'url': payload.url,
        'title': payload.title,
      },
    );
    return switch (raw) {
      'success' => 'share_completed',
      'dismissed' => 'share_cancelled',
      _ => null,
    };
  }

  Future<String?> _sendSharePlus(SharePayload payload) async {
    final result = await SharePlus.instance.share(
      ShareParams(
        text: payload.text,
        subject: payload.title,
        title: payload.title,
      ),
    );
    return switch (result.status) {
      ShareResultStatus.success => 'share_completed',
      ShareResultStatus.dismissed => 'share_cancelled',
      ShareResultStatus.unavailable => null,
    };
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
    } catch (e) {
      if (!mounted) return;
      final raw = '$e';
      final blocked = raw.contains('objectionable_content') ||
          raw.contains('user_inactive');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            blocked ? '이 내용은 등록할 수 없어요.' : '댓글을 남기지 못했어요.',
          ),
        ),
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Widget _navBar({
    required VoidCallback onBack,
    bool showActions = false,
  }) {
    final issue = _issue;
    final showIssueActions =
        showActions && issue != null && issue.contentKind.toUpperCase() != 'NEWS';
    return ScreenTopBar(
      title: '',
      leading: IconButton(
        onPressed: onBack,
        icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18),
        tooltip: '뒤로',
      ),
      trailing: showActions && issue != null
          ? Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (showIssueActions)
                  IconButton(
                    onPressed: _toggleFollow,
                    icon: Icon(
                      issue.isFollowing ? Icons.bookmark : Icons.bookmark_outline,
                      size: 22,
                      color: issue.isFollowing
                          ? TakeleyColors.accent
                          : TakeleyColors.fg,
                    ),
                    tooltip: issue.isFollowing ? '팔로우 해제' : '이슈 팔로우',
                  ),
                IconButton(
                  onPressed: _shareBusy ? null : _share,
                  icon: const Icon(Icons.ios_share_rounded, size: 22),
                  tooltip: '공유',
                ),
              ],
            )
          : null,
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
                  safetyApi: widget.safetyApi,
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
    final showDist = hasTake && issue.distributionVisible && totalVotes > 0;
    final fmt = NumberFormat.decimalPattern('ko_KR');
    final changing = hasTake &&
        _pendingOptionId != null &&
        _pendingOptionId != issue.myOptionId;
    return KeyedSubtree(
      key: _takePanelKey,
      child: Container(
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
              final selected = changing
                  ? _pendingOptionId == opt.id
                  : hasTake
                      ? issue.myOptionId == opt.id
                      : _pendingOptionId == opt.id;
              final pct = totalVotes > 0
                  ? ((opt.count / totalVotes) * 100).round()
                  : 0;
              // Count lives in the footer (“N명 생각 남김”); keep option meta to %.
              final meta = showDist ? '$pct%' : '';
              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: TakeleyVoteOptionButton(
                  label: opt.label,
                  meta: meta,
                  selected: selected,
                  enabled: !_voting,
                  fillFraction: showDist ? pct / 100.0 : null,
                  onPressed: () => _pickOption(opt.id),
                ),
              );
            }),
            if ((!hasTake && _pendingOptionId != null) || changing) ...[
              const SizedBox(height: 4),
              TakeleyOffsetPillButton(
                label: _voting
                    ? '결과 여는 중…'
                    : changing
                        ? '입장 바꾸기'
                        : '이걸로 남기고 결과 보기',
                enabled: !_voting,
                onPressed: _confirmVote,
              ),
              const SizedBox(height: 10),
            ],
            Text(
              hasTake
                  ? (totalVotes > 0
                      ? (showDist
                          ? '${fmt.format(issue.participationCount)}명 생각 남김'
                          : '${fmt.format(issue.participationCount)}명 생각 남김 · 비율은 더 모이면 공개')
                      : '아직 충분한 응답이 모이지 않았어요.')
                  : _pendingOptionId == null
                      ? '선택한 뒤에 다른 사람 생각을 볼 수 있어요.'
                      : '다른 선택지를 누르면 바꿀 수 있어요.',
              style: const TextStyle(color: TakeleyColors.muted, fontSize: 13),
            ),
            if (hasTake) ...[
              const SizedBox(height: 14),
              _judgmentNoteSection(issue),
              if (_otherTake != null) ...[
                const SizedBox(height: 16),
                _otherTakeCard(_otherTake!),
              ],
              const SizedBox(height: 12),
              TakeleySecondaryPillButton(
                label: '친구에게 묻기',
                enabled: !_shareBusy,
                onPressed: _share,
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _judgmentNoteSection(Issue issue) {
    final existing = (issue.myNote ?? '').trim();
    final hasNote = existing.isNotEmpty;

    if (hasNote) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '내가 남긴 한 줄',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.4,
              color: TakeleyColors.accent,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            existing,
            style: const TextStyle(
              fontSize: 15,
              height: 1.4,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 8),
          TextButton(
            onPressed: _savingNote ? null : _openJudgmentNoteSheet,
            style: TextButton.styleFrom(
              foregroundColor: TakeleyColors.muted,
              padding: EdgeInsets.zero,
              minimumSize: Size.zero,
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            child: const Text('고치기', style: TextStyle(fontSize: 13)),
          ),
        ],
      );
    }

    return TakeleySecondaryPillButton(
      label: '왜 그렇게 봤는지, 한 줄만 남겨둘래요',
      enabled: !_savingNote,
      onPressed: _openJudgmentNoteSheet,
    );
  }

  Widget _otherTakeCard(Map<String, dynamic> card) {
    final note = '${card['note'] ?? ''}';
    final label = '${card['option_label'] ?? ''}';
    final sameSide = card['same_side'] == true;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: TakeleyColors.hairline),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            sameSide ? '같은 입장의 다른 이유' : '다른 관점',
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: TakeleyColors.accent,
            ),
          ),
          if (label.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              label,
              style: const TextStyle(
                fontSize: 12,
                color: TakeleyColors.muted,
              ),
            ),
          ],
          const SizedBox(height: 8),
          Text(
            note,
            style: const TextStyle(fontSize: 15, height: 1.4),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              TextButton(
                onPressed: _openOtherTake,
                child: const Text('열기'),
              ),
              TextButton(
                onPressed: _skipOtherTake,
                child: const Text('넘어가기'),
              ),
            ],
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
    final isNews = issue.contentKind.toUpperCase() == 'NEWS';
    final imageUrl = resolveImageUrl(issue.imageUrl);
    final metaParts = <String>[];
    if (issue.sourceCount > 0) metaParts.add('출처 ${issue.sourceCount}');
    final sources = issue.sources.take(8).toList();
    final canWriteDeep =
        !isNews && showDeepThoughtWriterCta(_contributorStatus);
    // NEWS has no columnist essay — never show column CTA / byline.
    final hasColumn = !isNews && issue.columnBody.trim().isNotEmpty;
    final canVote = !isNews && _canVote(issue);

    return ListView(
      controller: _scroll,
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
        // NEWS: hero image then markdown briefing (## / **).
        if (isNews && imageUrl != null) ...[
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
        if (isNews && issue.columnBody.trim().isNotEmpty) ...[
          const SizedBox(height: 28),
          ColumnMarkdownView(source: issue.columnBody.trim()),
        ],
        if (!isNews && (issue.columnAuthorName ?? '').trim().isNotEmpty)
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
        if (!isNews && imageUrl != null) ...[
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
        if (canVote) _votePanel(issue),
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
        if (!canVote) _votePanel(issue),
        if (hasColumn)
          _columnCta(
            onTap: _openColumns,
            hint: '이 이슈를 긴 글로 읽어 보세요',
          ),
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
          child: TakeleySecondaryPillButton(
            label: _submitting ? '남기는 중…' : '남기기',
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
          const Text(
            '부적절한 댓글은 신고하거나 숨길 수 있어요.',
            style: TextStyle(color: TakeleyColors.muted, fontSize: 13),
          ),
          const SizedBox(height: 8),
          ..._comments.map((c) {
            final name = (c.displayName ?? '').trim();
            final mine = _userId != null && c.userId == _userId;
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
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          name.isEmpty ? '익명' : name,
                          style: const TextStyle(
                            fontWeight: FontWeight.w600,
                            fontSize: 13,
                            color: TakeleyColors.muted,
                          ),
                        ),
                      ),
                      IconButton(
                        icon: const Icon(Icons.more_horiz, size: 20),
                        tooltip: '더보기',
                        visualDensity: VisualDensity.compact,
                        onPressed: () => unawaited(
                          showUgcActions(
                            context: context,
                            safetyApi: widget.safetyApi,
                            targetType: 'comment',
                            targetId: c.id,
                            authorId: c.userId,
                            viewerId: _userId,
                            isMine: mine,
                            onRemovedFromFeed: () {
                              setState(() {
                                _comments =
                                    _comments.where((x) => x.id != c.id).toList();
                                if (_issue != null && mine) {
                                  _issue = _issue!.copyWith(
                                    commentCount:
                                        (_issue!.commentCount - 1).clamp(0, 999999),
                                  );
                                }
                              });
                            },
                            onDeleteOwn: mine
                                ? () => widget.safetyApi.deleteComment(
                                      commentId: c.id,
                                      userId: _userId,
                                    )
                                : null,
                          ),
                        ),
                      ),
                    ],
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
