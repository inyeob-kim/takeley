import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../api/columnists_api.dart';
import '../api/models.dart';
import '../theme/takeley_colors.dart';
import '../utils/category_label.dart';
import '../utils/format_news_time.dart';
import '../utils/resolve_image.dart';
import '../widgets/data_state.dart';
import '../widgets/profile_chrome.dart';

class ColumnistProfileScreen extends StatefulWidget {
  const ColumnistProfileScreen({
    super.key,
    required this.columnistId,
    required this.columnistsApi,
    required this.onIssueOpen,
  });

  final String columnistId;
  final ColumnistsApi columnistsApi;
  final ValueChanged<String> onIssueOpen;

  @override
  State<ColumnistProfileScreen> createState() => _ColumnistProfileScreenState();
}

class _ColumnistProfileScreenState extends State<ColumnistProfileScreen> {
  static const _pageSize = 10;

  ColumnistProfile? _profile;
  List<ColumnistIssueCard> _issues = [];
  int _issueCount = 0;
  bool _loading = true;
  bool _loadingMore = false;
  String? _error;

  bool get _canLoadMore => _issues.length < _issueCount;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final profile = await widget.columnistsApi.fetchProfile(widget.columnistId);
      if (!mounted) return;
      setState(() {
        _profile = profile;
        _issues = List.of(profile.issues);
        _issueCount = profile.issueCount;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = '프로필을 불러오지 못했어요.';
      });
    }
  }

  Future<void> _loadMore() async {
    if (_loadingMore || !_canLoadMore) return;
    setState(() => _loadingMore = true);
    try {
      final page = await widget.columnistsApi.fetchIssues(
        widget.columnistId,
        offset: _issues.length,
        limit: _pageSize,
      );
      if (!mounted) return;
      final seen = _issues.map((e) => e.id).toSet();
      setState(() {
        _issues = [
          ..._issues,
          ...page.items.where((e) => !seen.contains(e.id)),
        ];
        _issueCount = page.count;
        _loadingMore = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _loadingMore = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final profile = _profile;
    return Scaffold(
      backgroundColor: TakeleyColors.canvas,
      body: SafeArea(
        child: Column(
          children: [
            ScreenTopBar(
              title: '',
              afterGap: 8,
              leading: IconButton(
                onPressed: () => Navigator.of(context).pop(),
                icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18),
                tooltip: '뒤로',
              ),
            ),
            Expanded(
              child: _loading
                  ? const Center(
                      child: CircularProgressIndicator(
                        color: TakeleyColors.accent,
                      ),
                    )
                  : _error != null
                      ? DataState(
                          message: _error!,
                          actionLabel: '다시 시도',
                          onAction: () => unawaited(_load()),
                        )
                      : profile == null
                          ? const DataState(message: '프로필을 찾을 수 없어요.')
                          : ListView(
                              padding:
                                  const EdgeInsets.fromLTRB(20, 8, 20, 40),
                              children: [
                                const Text(
                                  '테이클리 칼럼니스트',
                                  style: TextStyle(
                                    fontSize: 11,
                                    fontWeight: FontWeight.w700,
                                    letterSpacing: 0.7,
                                    color: TakeleyColors.accent,
                                  ),
                                ),
                                const SizedBox(height: 14),
                                _header(profile),
                                if (profile.specialties.isNotEmpty) ...[
                                  const SizedBox(height: 20),
                                  _specialties(profile.specialties),
                                ],
                                if (profile.bio.trim().isNotEmpty) ...[
                                  const SizedBox(height: 18),
                                  _bioBlock(profile.bio.trim()),
                                ],
                                const SizedBox(height: 28),
                                Text(
                                  _issueCount == 0
                                      ? '칼럼'
                                      : '칼럼 · $_issueCount',
                                  style: const TextStyle(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w700,
                                    letterSpacing: 0.2,
                                    color: TakeleyColors.fg,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                if (_issues.isEmpty)
                                  const Padding(
                                    padding: EdgeInsets.only(top: 16),
                                    child: Text(
                                      '아직 공개된 칼럼이 없어요.',
                                      style: TextStyle(
                                        fontSize: 15,
                                        color: TakeleyColors.muted,
                                        height: 1.5,
                                      ),
                                    ),
                                  )
                                else ...[
                                  ..._issueList(_issues),
                                  if (_canLoadMore)
                                    Padding(
                                      padding: const EdgeInsets.only(top: 8),
                                      child: TextButton(
                                        onPressed: _loadingMore
                                            ? null
                                            : () => unawaited(_loadMore()),
                                        child: Text(
                                          _loadingMore
                                              ? '불러오는 중…'
                                              : '이전 칼럼 더 보기',
                                        ),
                                      ),
                                    ),
                                ],
                              ],
                            ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _header(ColumnistProfile profile) {
    final image = resolveImageUrl(profile.imageUrl);
    final initial = profile.displayName.trim().isNotEmpty
        ? String.fromCharCodes(profile.displayName.runes.take(1))
        : '?';
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        ClipOval(
          child: SizedBox(
            width: 72,
            height: 72,
            child: image != null
                ? CachedNetworkImage(
                    imageUrl: image,
                    fit: BoxFit.cover,
                    errorWidget: (_, __, ___) => _initialAvatar(initial),
                  )
                : _initialAvatar(initial),
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                profile.displayName,
                style: const TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w800,
                  letterSpacing: -0.4,
                  height: 1.25,
                  color: TakeleyColors.fg,
                ),
              ),
              if (profile.headline.trim().isNotEmpty) ...[
                const SizedBox(height: 6),
                Text(
                  profile.headline.trim(),
                  style: const TextStyle(
                    fontSize: 15,
                    height: 1.4,
                    color: TakeleyColors.muted,
                  ),
                ),
              ],
              if ((profile.email ?? '').trim().isNotEmpty) ...[
                const SizedBox(height: 6),
                Text(
                  profile.email!.trim(),
                  style: const TextStyle(
                    fontSize: 14,
                    height: 1.35,
                    color: TakeleyColors.muted,
                  ),
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }

  Widget _initialAvatar(String initial) {
    return ColoredBox(
      color: TakeleyColors.accentSoft,
      child: Center(
        child: Text(
          initial,
          style: const TextStyle(
            color: TakeleyColors.accent,
            fontWeight: FontWeight.w700,
            fontSize: 24,
          ),
        ),
      ),
    );
  }

  Widget _specialties(List<String> items) {
    return Wrap(
      spacing: 8,
      runSpacing: 6,
      children: [
        for (var i = 0; i < items.length; i++)
          Text(
            i == items.length - 1 ? items[i] : '${items[i]} ·',
            style: const TextStyle(
              fontSize: 14,
              height: 1.35,
              color: TakeleyColors.muted,
            ),
          ),
      ],
    );
  }

  Widget _bioBlock(String bio) {
    final lines = bio
        .split(RegExp(r'\r?\n'))
        .map((e) => e.trim())
        .where((e) => e.isNotEmpty)
        .toList();
    if (lines.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ...lines.map(
          (line) => Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(
              line,
              style: const TextStyle(
                fontSize: 16,
                height: 1.55,
                color: TakeleyColors.muted,
              ),
            ),
          ),
        ),
      ],
    );
  }

  List<Widget> _issueList(List<ColumnistIssueCard> issues) {
    final out = <Widget>[];
    for (var i = 0; i < issues.length; i++) {
      if (i > 0) {
        out.add(
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 2),
            child: Divider(height: 1, thickness: 1, color: TakeleyColors.border),
          ),
        );
      }
      out.add(_issueTile(issues[i]));
    }
    return out;
  }

  Widget _issueTile(ColumnistIssueCard item) {
    final when = formatNewsTime(
      issueStoryTimestamp(
        publishedAt: item.publishedAt,
        contentUpdatedAt: item.contentUpdatedAt,
      ),
    );
    final category = categoryLabel(item.category);
    final thumb = resolveImageUrl(item.imageUrl);
    final copy = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          item.title,
          style: const TextStyle(
            fontSize: 17,
            fontWeight: FontWeight.w700,
            height: 1.3,
            letterSpacing: -0.3,
            color: TakeleyColors.fg,
          ),
        ),
        if (item.summary.trim().isNotEmpty) ...[
          const SizedBox(height: 6),
          Text(
            item.summary.trim(),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 14,
              height: 1.45,
              color: TakeleyColors.muted,
            ),
          ),
        ],
        if (when.isNotEmpty) ...[
          const SizedBox(height: 8),
          Text(
            when,
            style: const TextStyle(
              fontSize: 12,
              color: TakeleyColors.muted,
            ),
          ),
        ],
      ],
    );
    return InkWell(
      onTap: () => widget.onIssueOpen(item.id),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              category.toUpperCase(),
              style: const TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.7,
                color: TakeleyColors.accent,
              ),
            ),
            const SizedBox(height: 6),
            thumb == null
                ? copy
                : Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(child: copy),
                      const SizedBox(width: 12),
                      _TrailingThumb(url: thumb),
                    ],
                  ),
          ],
        ),
      ),
    );
  }
}

class _TrailingThumb extends StatelessWidget {
  const _TrailingThumb({required this.url});

  final String url;
  static const double size = 72;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(10),
      child: SizedBox(
        width: size,
        height: size,
        child: CachedNetworkImage(
          imageUrl: url,
          fit: BoxFit.cover,
          errorWidget: (_, __, ___) => ColoredBox(
            color: TakeleyColors.pill,
            child: Icon(
              Icons.image_outlined,
              size: 22,
              color: TakeleyColors.secondaryLabel,
            ),
          ),
        ),
      ),
    );
  }
}
