import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../api/contributor_api.dart';
import '../api/safety_api.dart';
import '../theme/takeley_colors.dart';
import '../widgets/ugc_actions.dart';
import '../utils/contributor_ui.dart';
import '../widgets/data_state.dart';
import '../widgets/takeley_buttons.dart';

String? _errorMessage(Object e) {
  final raw = e.toString();
  if (raw.startsWith('Exception: ')) {
    return raw.substring('Exception: '.length);
  }
  return raw;
}

String _hostname(String url) {
  final u = Uri.tryParse(url);
  if (u != null && u.host.isNotEmpty) return u.host;
  return url;
}

class DeepThoughtDetailScreen extends StatefulWidget {
  const DeepThoughtDetailScreen({
    super.key,
    required this.contributorApi,
    required this.safetyApi,
    required this.issueId,
    required this.takeId,
    this.userId,
    required this.onBack,
  });

  final ContributorApi contributorApi;
  final SafetyApi safetyApi;
  final String issueId;
  final String takeId;
  final String? userId;
  final VoidCallback onBack;

  @override
  State<DeepThoughtDetailScreen> createState() =>
      _DeepThoughtDetailScreenState();
}

class _DeepThoughtDetailScreenState extends State<DeepThoughtDetailScreen> {
  IssueTake? _take;
  bool _loading = true;
  String? _error;
  bool _reactBusy = false;
  String? _reactHint;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
      _reactHint = null;
    });
    try {
      final row = await widget.contributorApi.fetchIssueTake(
        widget.issueId,
        widget.takeId,
        userId: widget.userId,
      );
      if (!mounted) return;
      setState(() {
        _take = row;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = formatContributorApiError(
          _errorMessage(e),
          '생각을 불러오지 못했어요',
        );
      });
    }
  }

  Future<void> _onReact() async {
    final take = _take;
    if (take == null || _reactBusy) return;
    setState(() {
      _reactBusy = true;
      _reactHint = null;
    });
    try {
      final result = await widget.contributorApi.reactToTake(
        issueId: widget.issueId,
        takeId: take.id,
        userId: widget.userId,
      );
      if (!mounted) return;
      setState(() {
        _take = take.copyWith(reactionCount: result.reactionCount);
        if (result.alreadyReacted) {
          _reactHint = '이미 공감한 생각이에요.';
        }
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _reactHint = formatContributorApiError(
          _errorMessage(e),
          '공감에 실패했어요',
        );
      });
    } finally {
      if (mounted) setState(() => _reactBusy = false);
    }
  }

  List<String> _paragraphs(String body) {
    return body
        .split(RegExp(r'\n\s*\n'))
        .map((p) => p.trim())
        .where((p) => p.isNotEmpty)
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    final fmt = NumberFormat.decimalPattern('ko_KR');
    final take = _take;

    return Scaffold(
      backgroundColor: TakeleyColors.canvas,
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              margin: const EdgeInsets.only(bottom: 12),
              padding: const EdgeInsets.fromLTRB(12, 4, 20, 4),
              decoration: const BoxDecoration(
                border: Border(
                  bottom: BorderSide(color: TakeleyColors.border, width: 1),
                ),
              ),
              child: Row(
                children: [
                  IconButton(
                    onPressed: widget.onBack,
                    icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18),
                    tooltip: '이슈로 돌아가기',
                  ),
                  const Spacer(),
                  if (take != null && take.authorId != widget.userId)
                    IconButton(
                      icon: const Icon(Icons.more_horiz, size: 20),
                      tooltip: '더보기',
                      onPressed: () => showUgcActions(
                        context: context,
                        safetyApi: widget.safetyApi,
                        targetType: 'take',
                        targetId: take.id,
                        authorId: take.authorId,
                        viewerId: widget.userId,
                        isMine: false,
                        onRemovedFromFeed: widget.onBack,
                      ),
                    ),
                ],
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
                          onAction: _load,
                        )
                      : take == null
                          ? const DataState(message: '생각을 찾을 수 없어요.')
                          : ListView(
                              padding:
                                  const EdgeInsets.fromLTRB(20, 12, 20, 40),
                              children: [
                                const Text(
                                  'Contributor',
                                  style: TextStyle(
                                    fontSize: 11,
                                    fontWeight: FontWeight.w700,
                                    letterSpacing: 0.7,
                                    color: TakeleyColors.accent,
                                  ),
                                ),
                                const SizedBox(height: 6),
                                Text(
                                  (take.displayName ?? '').trim().isEmpty
                                      ? '익명'
                                      : take.displayName!.trim(),
                                  style: const TextStyle(
                                    color: Color(0xFF444444),
                                    fontSize: 14,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                                const SizedBox(height: 14),
                                Text(
                                  take.title,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w800,
                                    fontSize: 26,
                                    height: 1.25,
                                    letterSpacing: -0.4,
                                    color: TakeleyColors.fg,
                                  ),
                                ),
                                const SizedBox(height: 22),
                                ..._paragraphs(take.body).map(
                                  (p) => Padding(
                                    padding: const EdgeInsets.only(bottom: 16),
                                    child: Text(
                                      p,
                                      style: const TextStyle(
                                        fontSize: 17,
                                        height: 1.7,
                                        fontWeight: FontWeight.w400,
                                        color: TakeleyColors.fg,
                                        letterSpacing: -0.15,
                                      ),
                                    ),
                                  ),
                                ),
                                if (take.sourceUrls.isNotEmpty) ...[
                                  const SizedBox(height: 8),
                                  Wrap(
                                    crossAxisAlignment:
                                        WrapCrossAlignment.center,
                                    children: [
                                      const Text(
                                        '출처 ',
                                        style: TextStyle(
                                          fontWeight: FontWeight.w700,
                                          fontSize: 13,
                                          color: TakeleyColors.fg,
                                        ),
                                      ),
                                      for (var i = 0;
                                          i < take.sourceUrls.length;
                                          i++) ...[
                                        if (i > 0)
                                          const Text(
                                            ' · ',
                                            style: TextStyle(
                                              color: Color(0xFF444444),
                                            ),
                                          ),
                                        Text(
                                          _hostname(take.sourceUrls[i]),
                                          style: const TextStyle(
                                            color: TakeleyColors.accent,
                                            fontWeight: FontWeight.w700,
                                            fontSize: 13,
                                          ),
                                        ),
                                      ],
                                    ],
                                  ),
                                ],
                                const SizedBox(height: 18),
                                Text(
                                  '조회 ${fmt.format(take.viewCount)} · 공감 ${fmt.format(take.reactionCount)}',
                                  style: const TextStyle(
                                    color: Color(0xFF444444),
                                    fontSize: 13,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                                if (take.status == 'published') ...[
                                  const SizedBox(height: 16),
                                  Align(
                                    alignment: Alignment.centerLeft,
                                    child: TakeleyOffsetPillButton(
                                      label: '공감',
                                      fullWidth: false,
                                      minHeight: 44,
                                      fontSize: 14,
                                      shadowOffset: 3,
                                      enabled: !_reactBusy,
                                      onPressed: _onReact,
                                    ),
                                  ),
                                  if (_reactHint != null) ...[
                                    const SizedBox(height: 8),
                                    Text(
                                      _reactHint!,
                                      style: const TextStyle(
                                        color: TakeleyColors.muted,
                                        fontSize: 13,
                                      ),
                                    ),
                                  ],
                                ],
                              ],
                            ),
            ),
          ],
        ),
      ),
    );
  }
}
