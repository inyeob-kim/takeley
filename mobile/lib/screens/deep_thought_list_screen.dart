import 'dart:async';

import 'package:flutter/material.dart';

import '../api/contributor_api.dart';
import '../navigation/cupertino_nav.dart';
import '../theme/takeley_colors.dart';
import '../utils/contributor_ui.dart';
import '../widgets/data_state.dart';
import '../widgets/deep_thought_card.dart';
import '../widgets/profile_chrome.dart';
import '../widgets/takeley_buttons.dart';
import 'deep_thought_detail_screen.dart';

/// Full ranked list of published deep thoughts for one issue.
class DeepThoughtListScreen extends StatefulWidget {
  const DeepThoughtListScreen({
    super.key,
    required this.contributorApi,
    required this.issueId,
    required this.onBack,
    this.userId,
    this.initialTakes = const [],
    this.canWriteDeep = false,
    this.onWrite,
  });

  final ContributorApi contributorApi;
  final String issueId;
  final String? userId;
  final List<IssueTake> initialTakes;
  final VoidCallback onBack;
  final bool canWriteDeep;
  final VoidCallback? onWrite;

  @override
  State<DeepThoughtListScreen> createState() => _DeepThoughtListScreenState();
}

class _DeepThoughtListScreenState extends State<DeepThoughtListScreen> {
  late List<IssueTake> _takes;
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _takes = rankIssueTakes(widget.initialTakes);
    if (_takes.isEmpty) {
      _reload();
    }
  }

  Future<void> _reload() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final takes = await widget.contributorApi.fetchIssueTakes(
        widget.issueId,
        limit: 50,
      );
      if (!mounted) return;
      setState(() {
        _takes = rankIssueTakes(takes);
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = '생각을 불러오지 못했어요.';
      });
    }
  }

  Future<void> _openDetail(String takeId) async {
    await pushCupertinoPage(
      context,
      DeepThoughtDetailScreen(
        contributorApi: widget.contributorApi,
        issueId: widget.issueId,
        takeId: takeId,
        userId: widget.userId,
        onBack: () => Navigator.of(context).pop(),
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
            ScreenTopBar(
              title: '깊이 있는 생각',
              leading: IconButton(
                icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18),
                onPressed: widget.onBack,
                tooltip: '이슈로 돌아가기',
              ),
            ),
            Expanded(
              child: _loading && _takes.isEmpty
                  ? const Center(
                      child: CircularProgressIndicator(
                        color: TakeleyColors.accent,
                      ),
                    )
                  : _error != null && _takes.isEmpty
                      ? DataState(
                          message: _error!,
                          actionLabel: '다시 시도',
                          onAction: _reload,
                        )
                      : _takes.isEmpty
                          ? const DataState(message: '아직 남긴 생각이 없어요.')
                          : ListView(
                              padding:
                                  const EdgeInsets.fromLTRB(20, 0, 20, 40),
                              children: [
                                Text(
                                  '${_takes.length}개의 생각',
                                  style: const TextStyle(
                                    color: TakeleyColors.muted,
                                    fontSize: 14,
                                    height: 1.4,
                                  ),
                                ),
                                const SizedBox(height: 14),
                                for (final t in _takes)
                                  DeepThoughtCard(
                                    take: t,
                                    onTap: () =>
                                        unawaited(_openDetail(t.id)),
                                  ),
                                if (widget.canWriteDeep &&
                                    widget.onWrite != null) ...[
                                  const SizedBox(height: 8),
                                  TakeleyOffsetPillButton(
                                    label: '생각 더 깊게 남기기',
                                    onPressed: widget.onWrite!,
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
}
