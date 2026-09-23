import 'dart:async';

import 'package:flutter/material.dart';

import '../api/device_session.dart';
import '../api/issues_api.dart';
import '../api/models.dart';
import '../api/settings_api.dart';
import '../navigation/cupertino_nav.dart';
import '../theme/takeley_colors.dart';
import '../utils/tab_visibility_reload.dart';
import '../widgets/profile_chrome.dart';
import '../widgets/takeley_buttons.dart';

const _nickMin = 2;
const _nickMax = 16;

/// Mirrors `frontend/src/screens/ProfileScreen.tsx`.
class ProfileScreen extends StatefulWidget {
  const ProfileScreen({
    super.key,
    required this.settingsApi,
    required this.issuesApi,
    required this.session,
    required this.onOpenSettings,
    required this.onOpenActivity,
  });

  final SettingsApi settingsApi;
  final IssuesApi issuesApi;
  final DeviceSession session;
  final VoidCallback onOpenSettings;
  final VoidCallback onOpenActivity;

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen>
    with TabVisibilityReloadMixin {
  String? _displayName;
  int _voteCount = 0;
  int _followCount = 0;
  int _commentCount = 0;
  int? _takesCount;
  bool _loading = true;
  final _nickTick = ValueNotifier<int>(0);
  final _draftCtrl = TextEditingController();
  bool _nickSaving = false;
  String? _nickHint;
  String? _nickError;

  @override
  String get tabPath => '/profile';

  @override
  void onTabBecameVisible() {
    _load(silent: true);
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _draftCtrl.dispose();
    _nickTick.dispose();
    super.dispose();
  }

  Future<void> _load({bool silent = false}) async {
    if (!silent) setState(() => _loading = true);
    try {
      final settings =
          await widget.settingsApi.fetch(userId: widget.session.userId);
      MyActivity? activity;
      try {
        activity = await widget.issuesApi
            .fetchMyActivity(userId: widget.session.userId);
      } catch (_) {
        activity = null;
      }
      if (!mounted) return;
      setState(() {
        _displayName = settings.displayName;
        _voteCount = activity?.participations.length ?? 0;
        _followCount = activity?.followed.length ?? 0;
        _commentCount = activity?.comments.length ?? 0;
        _takesCount = activity?.contributorStats?.takesCount;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _loading = false);
    }
  }

  String _initials(String? name) {
    final t = (name ?? '').trim();
    if (t.isEmpty) return '?';
    final parts = t.split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
    if (parts.length >= 2) {
      final a = String.fromCharCodes(parts[0].runes.take(1));
      final b = String.fromCharCodes(parts[1].runes.take(1));
      return '$a$b'.toUpperCase();
    }
    return String.fromCharCodes(t.runes.take(2)).toUpperCase();
  }

  Future<void> _saveNickname() async {
    final trimmed = _draftCtrl.text.trim();
    final valid = trimmed.isEmpty ||
        (trimmed.length >= _nickMin && trimmed.length <= _nickMax);
    final dirty = trimmed != (_displayName ?? '');
    if (_nickSaving || !dirty || !valid) return;
    setState(() {
      _nickSaving = true;
      _nickError = null;
      _nickHint = null;
    });
    _nickTick.value++;
    try {
      final updated = await widget.settingsApi.update(
        userId: widget.session.userId,
        displayName: trimmed,
      );
      if (!mounted) return;
      setState(() {
        _displayName = updated.displayName;
        _draftCtrl.text = updated.displayName ?? '';
        _nickHint = updated.displayName != null
            ? '닉네임을 저장했어요.'
            : '닉네임을 지웠어요. 익명으로 보여요.';
      });
      _nickTick.value++;
      FocusManager.instance.primaryFocus?.unfocus();
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _nickError = '닉네임을 저장하지 못했어요.';
      });
      _nickTick.value++;
    } finally {
      if (mounted) {
        setState(() => _nickSaving = false);
        _nickTick.value++;
      }
    }
  }

  Future<void> _openNicknamePanel() async {
    _draftCtrl.text = _displayName ?? '';
    _nickHint = null;
    _nickError = null;
    _nickTick.value++;
    await pushCupertinoPage(
      context,
      ListenableBuilder(
        listenable: Listenable.merge([_draftCtrl, _nickTick]),
        builder: (context, _) {
          final trimmed = _draftCtrl.text.trim();
          final valid = trimmed.isEmpty ||
              (trimmed.length >= _nickMin && trimmed.length <= _nickMax);
          final dirty = trimmed != (_displayName ?? '');
          return Scaffold(
            backgroundColor: TakeleyColors.canvas,
            body: SafeArea(
              child: Column(
                children: [
                  ScreenTopBar(
                    title: '닉네임',
                    leading: IconButton(
                      icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18),
                      onPressed: () => Navigator.of(context).pop(),
                    ),
                  ),
                  Expanded(
                    child: ListView(
                      padding: const EdgeInsets.fromLTRB(20, 0, 20, 40),
                      children: [
                        const ProfileBlockLabel('표시 이름'),
                        TextField(
                          controller: _draftCtrl,
                          maxLength: _nickMax,
                          enabled: !_nickSaving,
                          decoration: const InputDecoration(
                            hintText: '비우면 익명',
                            counterText: '',
                          ),
                          onTapOutside: (_) =>
                              FocusManager.instance.primaryFocus?.unfocus(),
                          onChanged: (_) {
                            _nickHint = null;
                            _nickTick.value++;
                          },
                        ),
                        const SizedBox(height: 8),
                        Text(
                          !valid
                              ? '$_nickMin–$_nickMax자로 입력해 주세요.'
                              : (_nickHint ?? '댓글·깊이 있는 생각에 보여요.'),
                          style: TextStyle(
                            color: !valid || _nickError != null
                                ? TakeleyColors.danger
                                : TakeleyColors.secondaryLabel,
                            fontSize: 13,
                          ),
                        ),
                        if (_nickError != null)
                          Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: Text(
                              _nickError!,
                              style: const TextStyle(
                                color: TakeleyColors.danger,
                                fontSize: 13,
                              ),
                            ),
                          ),
                        const SizedBox(height: 16),
                        TakeleyPrimaryButton(
                          label: _nickSaving ? '저장 중…' : '저장',
                          enabled: !_nickSaving && dirty && valid,
                          onPressed: _saveNickname,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final emptyName = (_displayName ?? '').trim().isEmpty;
    final shown = emptyName ? '익명' : _displayName!.trim();

    return ColoredBox(
      color: TakeleyColors.canvas,
      child: Column(
        children: [
          ScreenTopBar(
            title: '프로필',
            trailing: IconButton(
              tooltip: '설정',
              onPressed: widget.onOpenSettings,
              icon: const Icon(Icons.settings_outlined, size: 22),
            ),
          ),
          Expanded(
            child: _loading
                ? const Center(
                    child: CircularProgressIndicator(
                      color: TakeleyColors.accent,
                    ),
                  )
                : ListView(
                    padding: const EdgeInsets.fromLTRB(20, 0, 20, 88),
                    children: [
                      GestureDetector(
                        onTap: () => unawaited(_openNicknamePanel()),
                        behavior: HitTestBehavior.opaque,
                        child: Padding(
                          padding: const EdgeInsets.fromLTRB(0, 12, 0, 30),
                          child: Column(
                            children: [
                              Container(
                                width: 96,
                                height: 96,
                                alignment: Alignment.center,
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  color: emptyName
                                      ? TakeleyColors.pill
                                      : TakeleyColors.canvas,
                                  border: Border.all(
                                    color: TakeleyColors.avatarRing,
                                    width: 3,
                                  ),
                                ),
                                child: Text(
                                  _initials(_displayName),
                                  style: TextStyle(
                                    color: emptyName
                                        ? TakeleyColors.secondaryLabel
                                        : TakeleyColors.fg,
                                    fontWeight: FontWeight.w700,
                                    fontSize: 32,
                                    letterSpacing: -0.5,
                                  ),
                                ),
                              ),
                              const SizedBox(height: 16),
                              Text(
                                shown,
                                style: const TextStyle(
                                  fontSize: 28,
                                  fontWeight: FontWeight.w800,
                                  letterSpacing: -0.5,
                                  height: 1.15,
                                  color: TakeleyColors.fg,
                                ),
                              ),
                              const SizedBox(height: 6),
                              const Text(
                                '탭해서 닉네임 변경',
                                style: TextStyle(
                                  color: TakeleyColors.secondaryLabel,
                                  fontSize: 14,
                                  height: 1.4,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const ProfileBlockLabel('내 활동'),
                      ProfilePillRow(
                        icon: Icons.chat_bubble_outline_rounded,
                        label: '참여한 이슈',
                        count: _voteCount,
                        onTap: widget.onOpenActivity,
                      ),
                      ProfilePillRow(
                        icon: Icons.bookmark_border_rounded,
                        label: '팔로우한 이슈',
                        count: _followCount,
                        onTap: widget.onOpenActivity,
                      ),
                      ProfilePillRow(
                        icon: Icons.forum_outlined,
                        label: '댓글',
                        count: _commentCount,
                        onTap: widget.onOpenActivity,
                      ),
                      if (_takesCount != null) ...[
                        const SizedBox(height: 16),
                        const ProfileBlockLabel('글'),
                        ProfilePillRow(
                          icon: Icons.article_outlined,
                          label: '깊이 있는 생각',
                          count: _takesCount!,
                          onTap: widget.onOpenActivity,
                        ),
                      ],
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}
