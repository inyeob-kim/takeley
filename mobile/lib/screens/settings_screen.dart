import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api/contributor_api.dart';
import '../api/device_session.dart';
import '../api/settings_api.dart';
import '../config.dart';
import '../navigation/cupertino_nav.dart';
import '../services/fcm_service.dart';
import '../theme/takeley_colors.dart';
import '../utils/contributor_ui.dart';
import '../utils/industries.dart';
import '../widgets/data_state.dart';
import '../widgets/profile_chrome.dart';
import '../widgets/takeley_buttons.dart';

/// Mirrors `frontend/src/screens/SettingsScreen.tsx` (notifications + contributor).
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({
    super.key,
    required this.settingsApi,
    required this.contributorApi,
    required this.session,
    required this.fcm,
    required this.onBack,
  });

  final SettingsApi settingsApi;
  final ContributorApi contributorApi;
  final DeviceSession session;
  final FcmService fcm;
  final VoidCallback onBack;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  bool _notifications = true;
  bool _loading = true;
  String? _error;
  ContributorMe? _contributor;
  final _motivation = TextEditingController();
  final Set<String> _selectedInterests = {};
  final _panelTick = ValueNotifier<int>(0);
  bool _applyBusy = false;
  String? _applyError;
  String? _applyHint;

  @override
  void initState() {
    super.initState();
    _motivation.addListener(_onApplyFormChanged);
    _load();
  }

  @override
  void dispose() {
    _motivation.removeListener(_onApplyFormChanged);
    _motivation.dispose();
    _panelTick.dispose();
    super.dispose();
  }

  void _onApplyFormChanged() {
    if (mounted) setState(() {});
    _panelTick.value++;
  }

  bool get _canSubmitApplication =>
      _motivation.text.trim().isNotEmpty && _selectedInterests.isNotEmpty;

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final s = await widget.settingsApi.fetch(userId: widget.session.userId);
      ContributorMe? me;
      try {
        me = await widget.contributorApi
            .fetchMe(userId: widget.session.userId);
      } catch (_) {
        me = null;
      }
      if (!mounted) return;
      setState(() {
        _notifications = s.notificationsEnabled;
        _contributor = me;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = '설정을 불러오지 못했어요.';
      });
    }
  }

  Future<void> _setNotifications(bool value) async {
    setState(() => _notifications = value);
    try {
      await widget.settingsApi.update(
        userId: widget.session.userId,
        notificationsEnabled: value,
      );
      if (value && !kIsWeb) {
        await widget.fcm.requestAndRegister();
      }
    } catch (_) {
      if (!mounted) return;
      setState(() => _notifications = !value);
    }
  }

  Future<void> _submitApplication() async {
    if (_applyBusy) return;
    final interests = kIssueIndustries
        .where(_selectedInterests.contains)
        .join(', ');
    if (_motivation.text.trim().isEmpty || interests.isEmpty) {
      setState(() => _applyError = '함께하고 싶은 이유와 관심 산업을 선택해 주세요.');
      return;
    }
    setState(() {
      _applyBusy = true;
      _applyError = null;
      _applyHint = null;
    });
    _panelTick.value++;
    try {
      final app = await widget.contributorApi.submitApplication(
        motivation: _motivation.text.trim(),
        interests: interests,
        userId: widget.session.userId,
      );
      if (!mounted) return;
      setState(() {
        _contributor = ContributorMe(
          userId: app.id,
          contributorStatus: app.contributorStatus ?? 'PENDING',
          displayName: _contributor?.displayName,
          application: app,
        );
        _applyHint = '신청이 접수됐어요. 심사 결과를 기다려 주세요.';
        _motivation.clear();
        _selectedInterests.clear();
      });
      FocusManager.instance.primaryFocus?.unfocus();
      _panelTick.value++;
      await _load();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _applyError = formatContributorApiError('$e', '신청에 실패했어요');
      });
      _panelTick.value++;
    } finally {
      if (mounted) {
        setState(() => _applyBusy = false);
        _panelTick.value++;
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final status = _contributor?.contributorStatus ?? 'NONE';

    return Scaffold(
      backgroundColor: TakeleyColors.canvas,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            ScreenTopBar(
              title: '설정',
              leading: IconButton(
                icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18),
                onPressed: widget.onBack,
                tooltip: '프로필로 돌아가기',
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
                      : ListView(
                          padding: const EdgeInsets.fromLTRB(20, 0, 20, 40),
                          children: [
                            const ProfileBlockLabel('알림'),
                            ProfilePillRow(
                              icon: Icons.notifications_outlined,
                              label: '새 이슈 알림',
                              trailing: Switch.adaptive(
                                value: _notifications,
                                activeTrackColor: TakeleyColors.switchOn,
                                activeThumbColor: Colors.white,
                                onChanged: _setNotifications,
                              ),
                            ),
                            const SizedBox(height: 16),
                            const ProfileBlockLabel('글 쓰는 분'),
                            ProfilePillRow(
                              icon: Icons.edit_note_rounded,
                              label: '깊이 있는 생각',
                              value: contributorSettingsLabel(status),
                              onTap: () => unawaited(_openContributorPanel()),
                            ),
                            const SizedBox(height: 16),
                            const ProfileBlockLabel('정보'),
                            ProfilePillRow(
                              icon: Icons.info_outline_rounded,
                              label: '버전',
                              trailing: Text(
                                kAppVersion,
                                style: const TextStyle(
                                  fontSize: 15,
                                  fontWeight: FontWeight.w500,
                                  color: TakeleyColors.secondaryLabel,
                                ),
                              ),
                            ),
                            ProfilePillRow(
                              icon: Icons.gavel_outlined,
                              label: '이용약관',
                              onTap: () => unawaited(_openUrl(kTermsUrl)),
                            ),
                            ProfilePillRow(
                              icon: Icons.policy_outlined,
                              label: '개인정보 처리방침',
                              onTap: () => unawaited(_openUrl(kPrivacyUrl)),
                            ),
                            ProfilePillRow(
                              icon: Icons.mail_outline_rounded,
                              label: '고객지원',
                              onTap: () => unawaited(_openUrl(kSupportUrl)),
                            ),
                            ProfilePillRow(
                              icon: Icons.flag_outlined,
                              label: '부적절한 활동 신고',
                              onTap: () => unawaited(_openReportMail()),
                            ),
                            ProfilePillRow(
                              icon: Icons.delete_outline_rounded,
                              label: '내 데이터 삭제',
                              onTap: () => unawaited(_confirmDeleteData()),
                            ),
                            const SizedBox(height: 28),
                            const Text(
                              'Crafted for curious minds · TAKELEY',
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                color: TakeleyColors.craft,
                                fontSize: 12,
                                height: 1.4,
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

  Future<void> _openReportMail() async {
    final uri = Uri(
      scheme: 'mailto',
      path: kReportEmail,
      query: 'subject=TAKELEY 부적절한 활동 신고',
    );
    await _openUrl(uri.toString());
  }

  Future<void> _openUrl(String url) async {
    final uri = Uri.parse(url);
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('페이지를 열 수 없습니다.')),
      );
    }
  }

  Future<void> _confirmDeleteData() async {
    final ok = await showModalBottomSheet<bool>(
      context: context,
      backgroundColor: TakeleyColors.canvas,
      showDragHandle: true,
      useSafeArea: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) {
        return Padding(
          padding: const EdgeInsets.fromLTRB(20, 4, 20, 28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                '내 데이터를 삭제할까요?',
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                  letterSpacing: -0.4,
                  color: TakeleyColors.fg,
                  height: 1.25,
                ),
              ),
              const SizedBox(height: 6),
              const Text(
                '이 기기의 투표, 댓글, 알림이 삭제돼요. 앱은 익명으로 다시 시작돼요.',
                style: TextStyle(
                  fontSize: 15,
                  height: 1.45,
                  color: TakeleyColors.muted,
                ),
              ),
              const SizedBox(height: 20),
              TakeleyOffsetPillButton(
                label: '삭제',
                onPressed: () => Navigator.pop(ctx, true),
              ),
              const SizedBox(height: 10),
              TakeleySecondaryPillButton(
                label: '취소',
                minHeight: 52,
                fontSize: 16,
                onPressed: () => Navigator.pop(ctx, false),
              ),
            ],
          ),
        );
      },
    );
    if (ok != true || !mounted) return;
    try {
      await widget.session.deleteAccount();
      await widget.session.ensureRegistered(
        platform: FcmService.platformName(),
        appVersion: kAppVersion,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('데이터를 삭제했어요.')),
      );
      await _load();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('삭제하지 못했습니다. 잠시 후 다시 시도해 주세요.')),
      );
    }
  }

  Future<void> _openContributorPanel() async {
    await pushCupertinoPage(
      context,
      ListenableBuilder(
        listenable: Listenable.merge([_motivation, _panelTick]),
        builder: (context, _) => _buildContributorPanel(),
      ),
    );
    if (mounted) await _load();
  }

  Widget _buildContributorPanel() {
    final status = _contributor?.contributorStatus ?? 'NONE';
    final canApply = status == 'NONE' || status == 'REJECTED';

    return Scaffold(
      backgroundColor: TakeleyColors.canvas,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            ScreenTopBar(
              title: '깊이 있는 생각',
              leading: IconButton(
                icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18),
                onPressed: () => Navigator.of(context).pop(),
              ),
            ),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 40),
                children: [
                  const Text(
                    '당신의 생각을 테이클리에 남겨주세요',
                    style: TextStyle(
                      color: TakeleyColors.fg,
                      fontSize: 20,
                      fontWeight: FontWeight.w700,
                      height: 1.35,
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    '이슈를 깊이 있게 바라본 당신의 생각을 나눠주세요.\n'
                    '누군가에게는 새로운 관점이 될 수 있어요.\n'
                    '관심 있는 분야와 함께하고 싶은 이유를 알려주세요.',
                    style: TextStyle(
                      color: TakeleyColors.muted,
                      fontSize: 15,
                      height: 1.5,
                    ),
                  ),
                  const SizedBox(height: 16),
                  if (status == 'PENDING')
                    _statusCard('심사 중', '곧 테이클리 가족으로 함께할 수 있어요. 결과는 이 화면에서 확인할 수 있어요.'),
                  if (status == 'APPROVED')
                    _statusCard(
                      '함께하는 중',
                      '이슈 상세에서 깊이 있는 생각을 남길 수 있어요.',
                      ok: true,
                    ),
                  if (status == 'SUSPENDED')
                    _statusCard('이용 제한', '지금은 글 쓰는 기능을 이용할 수 없어요.'),
                  if (status == 'REJECTED')
                    _statusCard(
                      '반려',
                      '신청이 승인되지 않았어요.${_contributor?.application?.adminNote?.trim().isNotEmpty == true ? '\n${_contributor!.application!.adminNote!.trim()}' : ''}\n다시 신청할 수 있어요.',
                    ),
                  if (canApply) ...[
                    const SizedBox(height: 8),
                    _field('함께하고 싶은 이유', _motivation, '어떤 이슈에 대해 깊이 있는 생각을 나누고 싶나요?', 6),
                    _interestChips(),
                    if (_applyError != null)
                      Text(
                        _applyError!,
                        style: const TextStyle(color: TakeleyColors.danger),
                      ),
                    if (_applyHint != null)
                      Text(
                        _applyHint!,
                        style: const TextStyle(color: TakeleyColors.accent),
                      ),
                    const SizedBox(height: 12),
                    TakeleyOffsetPillButton(
                      label: _applyBusy ? '신청 중…' : '함께하기',
                      enabled: !_applyBusy && _canSubmitApplication,
                      onPressed: _submitApplication,
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

  Widget _statusCard(String kicker, String body, {bool ok = false}) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: TakeleyColors.pill,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            kicker,
            style: TextStyle(
              fontWeight: FontWeight.w700,
              color: ok ? TakeleyColors.accent : TakeleyColors.fg,
            ),
          ),
          const SizedBox(height: 6),
          Text(body, style: const TextStyle(height: 1.45)),
        ],
      ),
    );
  }

  Widget _interestChips() {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const ProfileBlockLabel('관심 있는 분야'),
          const SizedBox(height: 4),
          Text(
            '하나 이상 골라 주세요',
            style: TextStyle(
              fontSize: 13,
              color: TakeleyColors.muted,
              height: 1.35,
            ),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final label in kIssueIndustries)
                _InterestChip(
                  label: label,
                  selected: _selectedInterests.contains(label),
                  enabled: !_applyBusy,
                  onTap: () {
                    setState(() {
                      if (_selectedInterests.contains(label)) {
                        _selectedInterests.remove(label);
                      } else {
                        _selectedInterests.add(label);
                      }
                    });
                    _panelTick.value++;
                  },
                ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _field(
    String label,
    TextEditingController ctrl,
    String hint,
    int rows,
  ) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ProfileBlockLabel(label),
          TextField(
            controller: ctrl,
            minLines: rows,
            maxLines: rows + 4,
            enabled: !_applyBusy,
            onTapOutside: (_) => FocusManager.instance.primaryFocus?.unfocus(),
            decoration: InputDecoration(hintText: hint),
          ),
        ],
      ),
    );
  }
}

class _InterestChip extends StatelessWidget {
  const _InterestChip({
    required this.label,
    required this.selected,
    required this.enabled,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Opacity(
      opacity: enabled ? 1 : 0.5,
      child: GestureDetector(
        onTap: enabled ? onTap : null,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 160),
          curve: const Cubic(0.32, 0.72, 0, 1),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            color: selected ? TakeleyColors.accent : TakeleyColors.canvas,
            borderRadius: BorderRadius.circular(999),
            border: Border.all(
              color: selected ? TakeleyColors.accent : TakeleyColors.hairline,
            ),
          ),
          child: Text(
            label,
            style: TextStyle(
              color: selected ? Colors.white : const Color(0xFF444444),
              fontWeight: FontWeight.w600,
              fontSize: 14,
              letterSpacing: -0.28,
              height: 1.2,
            ),
          ),
        ),
      ),
    );
  }
}
