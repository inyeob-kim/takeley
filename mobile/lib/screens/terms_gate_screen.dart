import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../config.dart';
import '../theme/takeley_colors.dart';
import '../widgets/takeley_buttons.dart';

class TermsGateScreen extends StatefulWidget {
  const TermsGateScreen({super.key, required this.onAccepted});

  final VoidCallback onAccepted;

  @override
  State<TermsGateScreen> createState() => _TermsGateScreenState();
}

class _TermsGateScreenState extends State<TermsGateScreen> {
  bool _isAdult = false;
  bool _agreed = false;

  bool get _canContinue => _isAdult && _agreed;

  Future<void> _openTerms() async {
    final uri = Uri.parse(kTermsUrl);
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: TakeleyColors.canvas,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 28, 24, 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'TAKELEY',
                style: TextStyle(
                  color: TakeleyColors.accent,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0.04 * 16,
                  fontSize: 13,
                ),
              ),
              const SizedBox(height: 18),
              const Text(
                '시작하기 전에',
                style: TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.w800,
                  height: 1.25,
                  letterSpacing: -0.4,
                ),
              ),
              const SizedBox(height: 12),
              const Text(
                '만 18세 이상만 이용할 수 있어요.\n'
                '혐오·음란·괴롭힘은 허용하지 않으며, 신고는 24시간 안에 처리합니다.',
                style: TextStyle(
                  fontSize: 16,
                  height: 1.5,
                  color: TakeleyColors.muted,
                ),
              ),
              const Spacer(),
              _check(
                value: _isAdult,
                label: '만 18세 이상입니다',
                onChanged: (v) => setState(() => _isAdult = v),
              ),
              const SizedBox(height: 8),
              _check(
                value: _agreed,
                label: '이용약관에 동의합니다',
                onChanged: (v) => setState(() => _agreed = v),
              ),
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton(
                  onPressed: _openTerms,
                  child: const Text('이용약관 보기'),
                ),
              ),
              const SizedBox(height: 8),
              TakeleyOffsetPillButton(
                label: '동의하고 시작',
                enabled: _canContinue,
                onPressed: widget.onAccepted,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _check({
    required bool value,
    required String label,
    required ValueChanged<bool> onChanged,
  }) {
    return InkWell(
      onTap: () => onChanged(!value),
      child: Row(
        children: [
          Checkbox(
            value: value,
            activeColor: TakeleyColors.accent,
            onChanged: (v) => onChanged(v ?? false),
          ),
          Expanded(
            child: Text(
              label,
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }
}
