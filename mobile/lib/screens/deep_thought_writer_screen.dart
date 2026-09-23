import 'dart:async';

import 'package:flutter/material.dart';

import '../api/contributor_api.dart';
import '../theme/takeley_colors.dart';
import '../utils/contributor_ui.dart';
import '../widgets/takeley_buttons.dart';

typedef DeepThoughtSaved = ({String title, String body, List<String> sourceUrls});

DeepThoughtSaved? _savedSnapshot(IssueTake? take) {
  if (take == null) return null;
  return (title: take.title, body: take.body, sourceUrls: take.sourceUrls);
}

String? _errorMessage(Object e) {
  final raw = e.toString();
  if (raw.startsWith('Exception: ')) {
    return raw.substring('Exception: '.length);
  }
  return raw;
}

class DeepThoughtWriterScreen extends StatefulWidget {
  const DeepThoughtWriterScreen({
    super.key,
    required this.contributorApi,
    required this.issueId,
    required this.issueTitle,
    this.issueSummary = '',
    this.userId,
    this.initialTake,
    required this.onBack,
    this.onSaved,
  });

  final ContributorApi contributorApi;
  final String issueId;
  final String issueTitle;
  final String issueSummary;
  final String? userId;
  final IssueTake? initialTake;
  final VoidCallback onBack;
  final void Function(IssueTake take)? onSaved;

  @override
  State<DeepThoughtWriterScreen> createState() =>
      _DeepThoughtWriterScreenState();
}

class _DeepThoughtWriterScreenState extends State<DeepThoughtWriterScreen> {
  IssueTake? _take;
  late final TextEditingController _titleCtrl;
  late final TextEditingController _bodyCtrl;
  late final TextEditingController _sourcesCtrl;
  bool _busy = false;
  String? _error;
  String? _hint;
  bool _issueOpen = false;
  bool _sourcesOpen = false;

  @override
  void initState() {
    super.initState();
    _take = widget.initialTake;
    _titleCtrl = TextEditingController(text: widget.initialTake?.title ?? '');
    _bodyCtrl = TextEditingController(text: widget.initialTake?.body ?? '');
    final urls = widget.initialTake?.sourceUrls ?? const [];
    _sourcesCtrl = TextEditingController(text: urls.join('\n'));
    _sourcesOpen = urls.isNotEmpty;
  }

  @override
  void didUpdateWidget(DeepThoughtWriterScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.initialTake != widget.initialTake) {
      _applyTake(widget.initialTake);
    }
  }

  void _applyTake(IssueTake? take) {
    _take = take;
    _titleCtrl.text = take?.title ?? '';
    _bodyCtrl.text = take?.body ?? '';
    _sourcesCtrl.text = (take?.sourceUrls ?? const []).join('\n');
    _sourcesOpen = (take?.sourceUrls ?? const []).isNotEmpty;
    _error = null;
    _hint = null;
  }

  @override
  void dispose() {
    _titleCtrl.dispose();
    _bodyCtrl.dispose();
    _sourcesCtrl.dispose();
    super.dispose();
  }

  String get _status => _take?.status ?? 'draft';

  bool get _locked => isTakeEditingLocked(_status);

  bool get _canEdit => !_locked;

  bool get _dirty => isDeepThoughtDirty(
        _titleCtrl.text,
        _bodyCtrl.text,
        _sourcesCtrl.text,
        _savedSnapshot(_take),
      );

  bool get _canSave =>
      _canEdit &&
      !_busy &&
      canSaveDeepThought(
        _titleCtrl.text,
        _bodyCtrl.text,
        _sourcesCtrl.text,
        _savedSnapshot(_take),
      );

  Future<void> _handleBack() async {
    if (_canEdit && _dirty) {
      final leave = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('나가기'),
          content: const Text('저장하지 않은 내용이 있어요. 나가시겠어요?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('취소'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('나가기'),
            ),
          ],
        ),
      );
      if (leave != true || !mounted) return;
    }
    widget.onBack();
  }

  List<String>? _validate() {
    final result = validateDeepThoughtFields(
      _titleCtrl.text,
      _bodyCtrl.text,
      _sourcesCtrl.text,
    );
    if (!result.ok) {
      setState(() => _error = result.message);
      return null;
    }
    return result.sourceUrls;
  }

  Future<void> _onSave() async {
    if (_busy ||
        !_canEdit ||
        !canSaveDeepThought(
          _titleCtrl.text,
          _bodyCtrl.text,
          _sourcesCtrl.text,
          _savedSnapshot(_take),
        )) {
      return;
    }
    final urls = _validate();
    if (urls == null) return;
    setState(() {
      _busy = true;
      _error = null;
      _hint = null;
    });
    try {
      final IssueTake next;
      if (_take != null) {
        next = await widget.contributorApi.updateTake(
          issueId: widget.issueId,
          takeId: _take!.id,
          title: _titleCtrl.text.trim(),
          body: _bodyCtrl.text.trim(),
          sourceUrls: urls,
          userId: widget.userId,
        );
      } else {
        next = await widget.contributorApi.createTake(
          issueId: widget.issueId,
          title: _titleCtrl.text.trim(),
          body: _bodyCtrl.text.trim(),
          sourceUrls: urls,
          userId: widget.userId,
        );
      }
      if (!mounted) return;
      setState(() {
        _take = next;
        _titleCtrl.text = next.title;
        _bodyCtrl.text = next.body;
        _sourcesCtrl.text = next.sourceUrls.join('\n');
        _hint = '저장됐어요.';
      });
      widget.onSaved?.call(next);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = formatContributorApiError(
          _errorMessage(e),
          '저장하지 못했어요',
        );
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _onSubmitReview() async {
    if (_busy || !_canEdit) return;
    final urls = _validate();
    if (urls == null) return;
    setState(() {
      _busy = true;
      _error = null;
      _hint = null;
    });
    try {
      var current = _take;
      if (current == null) {
        current = await widget.contributorApi.createTake(
          issueId: widget.issueId,
          title: _titleCtrl.text.trim(),
          body: _bodyCtrl.text.trim(),
          sourceUrls: urls,
          userId: widget.userId,
        );
      } else if (_status == 'rejected' || _status == 'draft') {
        current = await widget.contributorApi.updateTake(
          issueId: widget.issueId,
          takeId: current.id,
          title: _titleCtrl.text.trim(),
          body: _bodyCtrl.text.trim(),
          sourceUrls: urls,
          userId: widget.userId,
        );
      }
      final next = await widget.contributorApi.submitTake(
        issueId: widget.issueId,
        takeId: current.id,
        userId: widget.userId,
      );
      if (!mounted) return;
      setState(() {
        _take = next;
        _hint = '검토 요청을 보냈어요.';
      });
      FocusManager.instance.primaryFocus?.unfocus();
      widget.onSaved?.call(next);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = formatContributorApiError(
          _errorMessage(e),
          '검토 요청에 실패했어요',
        );
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _onWithdraw() async {
    if (_busy || _take == null || _status != 'pending_review') return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final next = await widget.contributorApi.withdrawTake(
        issueId: widget.issueId,
        takeId: _take!.id,
        userId: widget.userId,
      );
      if (!mounted) return;
      setState(() {
        _take = next;
        _hint = '검토를 철회했어요. 다시 수정할 수 있어요.';
      });
      widget.onSaved?.call(next);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = formatContributorApiError(
          _errorMessage(e),
          '철회하지 못했어요',
        );
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final summaryText = widget.issueSummary.trim();
    final showFooter = _canEdit || _status == 'pending_review';
    final canSubmit = !_busy &&
        _titleCtrl.text.trim().isNotEmpty &&
        _bodyCtrl.text.trim().isNotEmpty;

    return PopScope(
      canPop: !_canEdit || !_dirty,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) unawaited(_handleBack());
      },
      child: Scaffold(
        backgroundColor: TakeleyColors.canvas,
        body: SafeArea(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _WriterNav(onBack: _busy ? null : _handleBack),
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(20, 14, 20, 24),
                  children: [
                    _IssueToggle(
                      open: _issueOpen,
                      title: widget.issueTitle,
                      onTap: () => setState(() => _issueOpen = !_issueOpen),
                    ),
                    if (_issueOpen) ...[
                      const SizedBox(height: 14),
                      Text(
                        widget.issueTitle,
                        style: const TextStyle(
                          fontWeight: FontWeight.w700,
                          fontSize: 17,
                          height: 1.35,
                          letterSpacing: -0.3,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        summaryText.isNotEmpty
                            ? summaryText
                            : '요약이 아직 없어요.',
                        style: TextStyle(
                          color: summaryText.isEmpty
                              ? TakeleyColors.muted
                              : const Color(0xFF444444),
                          height: 1.6,
                          fontSize: 15,
                        ),
                      ),
                    ],
                    if (_status == 'rejected' &&
                        (_take?.adminNote ?? '').trim().isNotEmpty) ...[
                      const SizedBox(height: 16),
                      _StatusBanner(
                        label: '검토 결과',
                        body: _take!.adminNote!.trim(),
                      ),
                    ],
                    if (_status == 'pending_review') ...[
                      const SizedBox(height: 16),
                      const Text(
                        '검토 중이에요. 결과가 나올 때까지 수정할 수 없어요.',
                        style: TextStyle(
                          color: TakeleyColors.muted,
                          fontSize: 14,
                          height: 1.5,
                        ),
                      ),
                    ],
                    if (_status == 'published') ...[
                      const SizedBox(height: 16),
                      const Text(
                        '게시된 생각은 수정할 수 없어요.',
                        style: TextStyle(
                          color: TakeleyColors.muted,
                          fontSize: 14,
                          height: 1.5,
                        ),
                      ),
                    ],
                    const SizedBox(height: 18),
                    TextField(
                      controller: _titleCtrl,
                      enabled: _canEdit && !_busy,
                      maxLength: 120,
                      style: const TextStyle(
                        fontWeight: FontWeight.w700,
                        fontSize: 22,
                        height: 1.3,
                        letterSpacing: -0.4,
                        color: TakeleyColors.fg,
                      ),
                      decoration: InputDecoration(
                        hintText: '이 생각을 한 줄로 요약해 주세요',
                        hintStyle: TextStyle(
                          color: TakeleyColors.muted.withValues(alpha: 0.7),
                          fontWeight: FontWeight.w600,
                          fontSize: 22,
                        ),
                        counterText: '',
                        filled: false,
                        contentPadding:
                            const EdgeInsets.fromLTRB(0, 8, 0, 12),
                        border: InputBorder.none,
                        enabledBorder: const UnderlineInputBorder(
                          borderSide:
                              BorderSide(color: TakeleyColors.border),
                        ),
                        focusedBorder: const UnderlineInputBorder(
                          borderSide: BorderSide(
                            color: TakeleyColors.accent,
                            width: 1.5,
                          ),
                        ),
                        disabledBorder: const UnderlineInputBorder(
                          borderSide:
                              BorderSide(color: TakeleyColors.border),
                        ),
                      ),
                      onChanged: (_) => setState(() {}),
                      onTapOutside: (_) =>
                          FocusManager.instance.primaryFocus?.unfocus(),
                    ),
                    const SizedBox(height: 8),
                    TextField(
                      controller: _bodyCtrl,
                      enabled: _canEdit && !_busy,
                      minLines: 14,
                      maxLines: null,
                      style: const TextStyle(
                        fontSize: 17,
                        height: 1.7,
                        color: TakeleyColors.fg,
                      ),
                      decoration: InputDecoration(
                        hintText:
                            '왜 그렇게 생각하는지, 어떤 점이 중요한지 자유롭게 적어 주세요.',
                        hintStyle: TextStyle(
                          color: TakeleyColors.muted.withValues(alpha: 0.75),
                          fontSize: 17,
                          height: 1.7,
                        ),
                        filled: false,
                        contentPadding: const EdgeInsets.symmetric(vertical: 6),
                        border: InputBorder.none,
                        enabledBorder: InputBorder.none,
                        focusedBorder: InputBorder.none,
                        disabledBorder: InputBorder.none,
                      ),
                      onChanged: (_) => setState(() {}),
                      onTapOutside: (_) =>
                          FocusManager.instance.primaryFocus?.unfocus(),
                    ),
                    const SizedBox(height: 20),
                    const Divider(height: 1, color: TakeleyColors.border),
                    const SizedBox(height: 14),
                    GestureDetector(
                      onTap: () =>
                          setState(() => _sourcesOpen = !_sourcesOpen),
                      child: Text(
                        _sourcesOpen ? '출처 접기' : '출처 추가 (선택)',
                        style: const TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: TakeleyColors.muted,
                        ),
                      ),
                    ),
                    if (_sourcesOpen) ...[
                      const SizedBox(height: 10),
                      TextField(
                        controller: _sourcesCtrl,
                        enabled: _canEdit && !_busy,
                        minLines: 3,
                        maxLines: 4,
                        style: const TextStyle(fontSize: 14, height: 1.45),
                        decoration: InputDecoration(
                          hintText: '참고한 링크를 한 줄에 하나씩\nhttps://…',
                          hintStyle: const TextStyle(
                            color: TakeleyColors.muted,
                            fontSize: 14,
                          ),
                          filled: true,
                          fillColor: TakeleyColors.soft,
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 14,
                            vertical: 12,
                          ),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(10),
                            borderSide:
                                const BorderSide(color: TakeleyColors.border),
                          ),
                          enabledBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(10),
                            borderSide:
                                const BorderSide(color: TakeleyColors.border),
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(10),
                            borderSide: const BorderSide(
                              color: TakeleyColors.accent,
                            ),
                          ),
                        ),
                        onChanged: (_) => setState(() {}),
                        onTapOutside: (_) =>
                            FocusManager.instance.primaryFocus?.unfocus(),
                      ),
                    ],
                    if (_error != null) ...[
                      const SizedBox(height: 14),
                      Text(
                        _error!,
                        style: const TextStyle(
                          color: TakeleyColors.danger,
                          fontSize: 13,
                          height: 1.45,
                        ),
                      ),
                    ],
                    if (_hint != null) ...[
                      const SizedBox(height: 14),
                      Text(
                        _take != null
                            ? '${_hint!} · ${takeStatusLabel(_take!.status)}'
                            : _hint!,
                        style: const TextStyle(
                          color: TakeleyColors.muted,
                          fontSize: 13,
                          height: 1.45,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              if (showFooter)
                Container(
                  padding: const EdgeInsets.fromLTRB(20, 12, 20, 12),
                  decoration: const BoxDecoration(
                    color: TakeleyColors.canvas,
                    border: Border(
                      top: BorderSide(color: TakeleyColors.border),
                    ),
                  ),
                  child: SafeArea(
                    top: false,
                    child: Row(
                      children: [
                        if (_canEdit) ...[
                          Expanded(
                            child: TakeleySecondaryPillButton(
                              label: '저장',
                              enabled: _canSave,
                              onPressed: _onSave,
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: TakeleyOffsetPillButton(
                              label: '검토 요청',
                              minHeight: 44,
                              fontSize: 15,
                              shadowOffset: 3,
                              enabled: canSubmit,
                              onPressed: _onSubmitReview,
                            ),
                          ),
                        ] else if (_status == 'pending_review')
                          Expanded(
                            child: TakeleySecondaryPillButton(
                              label: '검토 철회',
                              enabled: !_busy,
                              onPressed: _onWithdraw,
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _WriterNav extends StatelessWidget {
  const _WriterNav({required this.onBack});

  final VoidCallback? onBack;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(8, 4, 16, 8),
      decoration: const BoxDecoration(
        color: TakeleyColors.canvas,
        border: Border(
          bottom: BorderSide(color: TakeleyColors.border, width: 1),
        ),
      ),
      child: SizedBox(
        height: 44,
        child: Row(
          children: [
            IconButton(
              onPressed: onBack,
              icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18),
              tooltip: '이슈로 돌아가기',
            ),
          ],
        ),
      ),
    );
  }
}

class _IssueToggle extends StatelessWidget {
  const _IssueToggle({
    required this.open,
    required this.title,
    required this.onTap,
  });

  final bool open;
  final String title;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: TakeleyColors.soft,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: TakeleyColors.border),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                open ? '이슈 접기' : '이슈 보기',
                style: const TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.5,
                  color: TakeleyColors.accent,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                title,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  height: 1.4,
                  color: TakeleyColors.fg,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusBanner extends StatelessWidget {
  const _StatusBanner({required this.label, required this.body});

  final String label;
  final String body;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
      decoration: BoxDecoration(
        color: TakeleyColors.soft,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0x0F000000)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.4,
              color: TakeleyColors.muted,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            body,
            style: const TextStyle(
              fontSize: 14,
              height: 1.5,
              color: TakeleyColors.fg,
            ),
          ),
        ],
      ),
    );
  }
}
