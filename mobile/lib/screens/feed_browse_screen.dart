import 'dart:async';

import 'package:flutter/material.dart';

import '../api/device_session.dart';
import '../api/issues_api.dart';
import '../api/models.dart';
import '../theme/takeley_colors.dart';
import '../utils/industries.dart';
import '../widgets/data_state.dart';
import '../widgets/feed_chips.dart';
import '../widgets/issue_card.dart';
import '../widgets/profile_chrome.dart';

final _newsFeedTabs = <({String id, String label})>[
  (id: 'all', label: '전체'),
  ...kIssueIndustries.map((id) => (id: id, label: id)),
];

/// Push screen: ISSUE or NEWS list. Optional category chips under header.
class FeedBrowseScreen extends StatefulWidget {
  const FeedBrowseScreen({
    super.key,
    required this.issuesApi,
    required this.session,
    required this.contentKind,
    required this.title,
    required this.onIssueOpen,
    this.onIssueTake,
    this.onBack,
    this.showCategoryChips = false,
    this.sort = 'trending',
  });

  final IssuesApi issuesApi;
  final DeviceSession session;
  final String contentKind;
  final String title;
  final void Function(String id, {bool scrollToTake}) onIssueOpen;
  final ValueChanged<String>? onIssueTake;
  final VoidCallback? onBack;
  final bool showCategoryChips;
  final String sort;

  @override
  State<FeedBrowseScreen> createState() => _FeedBrowseScreenState();
}

class _FeedBrowseScreenState extends State<FeedBrowseScreen> {
  String _tab = 'all';
  List<Issue> _items = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final category =
          widget.showCategoryChips && _tab != 'all' ? _tab : null;
      final result = await widget.issuesApi.fetchIssues(
        limit: 40,
        sort: widget.sort,
        contentKind: widget.contentKind,
        category: category,
        userId: widget.session.userId,
      );
      if (!mounted) return;
      final kind = widget.contentKind.toUpperCase();
      final items = result.items
          .where((i) => i.contentKind.toUpperCase() == kind)
          .toList();
      setState(() {
        _items = items;
        _loading = false;
      });
      for (final issue in items.take(12)) {
        unawaited(widget.issuesApi.recordEvent(
          id: issue.id,
          event: 'impression',
          userId: widget.session.userId,
        ));
      }
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = widget.contentKind == 'NEWS'
            ? '뉴스를 불러오지 못했어요.\n잠시 후 다시 시도해 주세요.'
            : 'TAKE를 불러오지 못했어요.\n잠시 후 다시 시도해 주세요.';
      });
    }
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
    final bottomPad = MediaQuery.paddingOf(context).bottom;
    // Full-screen route (outside shell) — pad top for status bar / notch.
    return ColoredBox(
      color: TakeleyColors.canvas,
      child: SafeArea(
        bottom: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            ScreenTopBar(
              title: widget.title,
              afterGap: widget.showCategoryChips ? 8 : 14,
              leading: widget.onBack == null
                  ? null
                  : IconButton(
                      tooltip: '뒤로',
                      onPressed: widget.onBack,
                      icon: const Icon(
                        Icons.arrow_back_ios_new_rounded,
                        size: 18,
                      ),
                    ),
            ),
            if (widget.showCategoryChips)
              FeedChips(
                tabs: _newsFeedTabs,
                selectedId: _tab,
                onSelect: (id) {
                  setState(() => _tab = id);
                  _load();
                },
              ),
            Expanded(
              child: RefreshIndicator(
                color: TakeleyColors.accent,
                onRefresh: _load,
                child: _loading
                    ? ListView(
                        physics: const AlwaysScrollableScrollPhysics(),
                        children: const [
                          SizedBox(height: 120),
                          Center(
                            child: CircularProgressIndicator(
                              color: TakeleyColors.accent,
                            ),
                          ),
                        ],
                      )
                    : _error != null
                        ? ListView(
                            physics: const AlwaysScrollableScrollPhysics(),
                            children: [
                              SizedBox(
                                height:
                                    MediaQuery.sizeOf(context).height * 0.45,
                                child: DataState(
                                  message: _error!,
                                  actionLabel: '다시 시도',
                                  onAction: _load,
                                ),
                              ),
                            ],
                          )
                        : _items.isEmpty
                            ? ListView(
                                physics:
                                    const AlwaysScrollableScrollPhysics(),
                                children: [
                                  SizedBox(
                                    height: MediaQuery.sizeOf(context).height *
                                        0.45,
                                    child: DataState(
                                      message: widget.contentKind == 'NEWS'
                                          ? '아직 뉴스가 없어요.'
                                          : '아직 TAKE가 없어요.',
                                    ),
                                  ),
                                ],
                              )
                            : ListView.separated(
                                physics:
                                    const AlwaysScrollableScrollPhysics(),
                                padding:
                                    EdgeInsets.only(bottom: 24 + bottomPad),
                                itemCount: _items.length,
                                separatorBuilder: (_, __) => const Padding(
                                  padding:
                                      EdgeInsets.symmetric(horizontal: 20),
                                  child: Divider(height: 1, thickness: 2),
                                ),
                                itemBuilder: (context, index) {
                                  final issue = _items[index];
                                  return IssueCard(
                                    issue: issue,
                                    onOpen: _openCard,
                                    onCta: _ctaCard,
                                  );
                                },
                              ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
