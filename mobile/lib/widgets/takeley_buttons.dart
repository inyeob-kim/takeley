import 'package:flutter/material.dart';

import '../theme/takeley_colors.dart';

/// Finimize offset-shadow pill — React `.issue-column-cta` / `.issue-comment-submit`.
class TakeleyOffsetPillButton extends StatefulWidget {
  const TakeleyOffsetPillButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.enabled = true,
    this.fullWidth = true,
    this.minHeight = 52,
    this.fontSize = 16,
    this.shadowOffset = 4,
  });

  final String label;
  final VoidCallback? onPressed;
  final bool enabled;
  final bool fullWidth;
  final double minHeight;
  final double fontSize;
  final double shadowOffset;

  @override
  State<TakeleyOffsetPillButton> createState() =>
      _TakeleyOffsetPillButtonState();
}

class _TakeleyOffsetPillButtonState extends State<TakeleyOffsetPillButton> {
  bool _pressed = false;

  bool get _active => widget.enabled && widget.onPressed != null;

  @override
  Widget build(BuildContext context) {
    final shadow =
        !_active ? 0.0 : (_pressed ? widget.shadowOffset / 2 : widget.shadowOffset);
    final translate = _pressed && _active ? widget.shadowOffset / 2 : 0.0;

    return Opacity(
      opacity: _active ? 1 : 0.45,
      child: GestureDetector(
        onTapDown: _active ? (_) => setState(() => _pressed = true) : null,
        onTapUp: _active
            ? (_) {
                setState(() => _pressed = false);
                widget.onPressed?.call();
              }
            : null,
        onTapCancel: _active ? () => setState(() => _pressed = false) : null,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 80),
          transform: Matrix4.translationValues(translate, translate, 0),
          width: widget.fullWidth ? double.infinity : null,
          constraints: BoxConstraints(minHeight: widget.minHeight),
          padding: EdgeInsets.symmetric(
            horizontal: widget.fullWidth ? 20 : 22.4,
            vertical: widget.fullWidth ? 12 : 0,
          ),
          decoration: BoxDecoration(
            color: TakeleyColors.accent,
            borderRadius: BorderRadius.circular(999),
            boxShadow: shadow > 0
                ? [
                    BoxShadow(
                      color: TakeleyColors.fg,
                      offset: Offset(shadow, shadow),
                      blurRadius: 0,
                    ),
                  ]
                : const [],
          ),
          alignment: Alignment.center,
          child: Text(
            widget.label,
            style: TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w700,
              fontSize: widget.fontSize,
              letterSpacing: -0.3,
            ),
          ),
        ),
      ),
    );
  }
}

/// React `.issue-vote-btn` / `.is-selected`.
class TakeleyVoteOptionButton extends StatelessWidget {
  const TakeleyVoteOptionButton({
    super.key,
    required this.label,
    required this.meta,
    required this.selected,
    required this.onPressed,
    this.enabled = true,
  });

  final String label;
  final String meta;
  final bool selected;
  final VoidCallback? onPressed;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    return Opacity(
      opacity: enabled ? 1 : 0.7,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: enabled ? onPressed : null,
          borderRadius: BorderRadius.circular(12),
          child: Ink(
            decoration: BoxDecoration(
              color: selected ? TakeleyColors.accentSoft : Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: selected
                    ? TakeleyColors.accent
                    : TakeleyColors.accent.withValues(alpha: 0.35),
                width: 1.5,
              ),
            ),
            child: ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 52),
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 12,
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        label,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: TakeleyColors.fg,
                        ),
                      ),
                    ),
                    Text(
                      meta,
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w500,
                        color: TakeleyColors.muted,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Outline pill — React `.deep-thought-writer__btn--secondary`.
class TakeleySecondaryPillButton extends StatelessWidget {
  const TakeleySecondaryPillButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.enabled = true,
    this.minHeight = 44,
    this.fontSize = 15,
  });

  final String label;
  final VoidCallback? onPressed;
  final bool enabled;
  final double minHeight;
  final double fontSize;

  @override
  Widget build(BuildContext context) {
    final active = enabled && onPressed != null;
    return Opacity(
      opacity: active ? 1 : 0.35,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: active ? onPressed : null,
          borderRadius: BorderRadius.circular(999),
          child: Container(
            constraints: BoxConstraints(minHeight: minHeight),
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
            decoration: BoxDecoration(
              color: TakeleyColors.canvas,
              borderRadius: BorderRadius.circular(999),
              border: Border.all(color: const Color(0x1F000000)),
            ),
            alignment: Alignment.center,
            child: Text(
              label,
              style: TextStyle(
                fontSize: fontSize,
                fontWeight: FontWeight.w700,
                color: TakeleyColors.fg,
                letterSpacing: -0.2,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// React `.settings-primary-btn` — blue fill, 16 radius, no offset shadow.
class TakeleyPrimaryButton extends StatelessWidget {
  const TakeleyPrimaryButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.enabled = true,
  });

  final String label;
  final VoidCallback? onPressed;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    final active = enabled && onPressed != null;
    return SizedBox(
      width: double.infinity,
      height: 50,
      child: FilledButton(
        onPressed: active ? onPressed : null,
        style: FilledButton.styleFrom(
          backgroundColor: TakeleyColors.accent,
          disabledBackgroundColor:
              TakeleyColors.accent.withValues(alpha: 0.4),
          foregroundColor: Colors.white,
          disabledForegroundColor: Colors.white,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          textStyle: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
        child: Text(label),
      ),
    );
  }
}
