import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../api/models.dart';
import '../theme/takeley_colors.dart';
import '../utils/category_label.dart';
import '../utils/format_news_time.dart';
import '../utils/resolve_image.dart';

/// Where the cover sits relative to title/summary.
enum IssueCardImageLayout {
  /// Home feed — full-width image under summary.
  below,

  /// Activity follow list — small thumb on the right when present.
  trailing,
}

/// Mirrors `frontend/src/components/IssueCard.tsx`.
class IssueCard extends StatefulWidget {
  const IssueCard({
    super.key,
    required this.issue,
    required this.onOpen,
    this.imageLayout = IssueCardImageLayout.below,
    this.padding = const EdgeInsets.fromLTRB(20, 22, 20, 20),
    this.footerOverride,
    this.ctaLabel,
    this.takeLabel,
    this.showSummary = true,
  });

  final Issue issue;
  final ValueChanged<Issue> onOpen;
  final IssueCardImageLayout imageLayout;
  final EdgeInsetsGeometry padding;

  /// Optional subtitle under title (e.g. vote label on activity).
  final String? footerOverride;

  /// Footer CTA text. Defaults to 생각 남기기 / 자세히 보기.
  final String? ctaLabel;

  /// My take chip — activity 참여 목록.
  final String? takeLabel;

  final bool showSummary;

  @override
  State<IssueCard> createState() => _IssueCardState();
}

class _IssueCardState extends State<IssueCard> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    final issue = widget.issue;
    final when = formatNewsTime(
      issueStoryTimestamp(
        publishedAt: issue.publishedAt,
        firstSeenAt: issue.firstSeenAt,
        contentUpdatedAt: issue.contentUpdatedAt,
      ),
    );
    final canVote = issue.participationSuitable &&
        (issue.participationQuestion?.isNotEmpty ?? false);
    final cat = categoryLabel(issue.category);
    final imageUrl = resolveImageUrl(issue.imageUrl);
    final trend = issue.trendStatus.toUpperCase();
    final meta = _footerMeta(issue, when);
    final thumbUrl =
        widget.imageLayout == IssueCardImageLayout.trailing ? imageUrl : null;

    return GestureDetector(
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) => setState(() => _pressed = false),
      onTapCancel: () => setState(() => _pressed = false),
      onTap: () => widget.onOpen(issue),
      child: AnimatedOpacity(
        duration: const Duration(milliseconds: 100),
        opacity: _pressed ? 0.72 : 1,
        child: Padding(
          padding: widget.padding,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(cat, style: Theme.of(context).textTheme.labelLarge),
                  const Spacer(),
                  if (trend == 'TRENDING')
                    Text(
                      '🔥 지금 뜨는',
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                            color: TakeleyColors.rising,
                            fontWeight: FontWeight.w700,
                          ),
                    )
                  else if (trend == 'RISING')
                    Text(
                      '급상승',
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                            color: TakeleyColors.rising,
                            fontWeight: FontWeight.w600,
                          ),
                    ),
                ],
              ),
              const SizedBox(height: 10),
              if (thumbUrl != null)
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: _titleBlock(context, issue)),
                    const SizedBox(width: 12),
                    _TrailingThumb(url: thumbUrl),
                  ],
                )
              else ...[
                _titleBlock(context, issue),
                if (imageUrl != null) ...[
                  const SizedBox(height: 14),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    child: AspectRatio(
                      aspectRatio: 16 / 9,
                      child: CachedNetworkImage(
                        imageUrl: imageUrl,
                        fit: BoxFit.cover,
                        errorWidget: (_, __, ___) => const SizedBox.shrink(),
                      ),
                    ),
                  ),
                ],
              ],
              const SizedBox(height: 14),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      widget.footerOverride ??
                          (meta.isEmpty ? '이슈' : meta),
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ),
                  Text(
                    widget.ctaLabel ??
                        (canVote ? '생각 남기기 →' : '자세히 보기 →'),
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: TakeleyColors.accent,
                          fontWeight: FontWeight.w600,
                        ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _titleBlock(BuildContext context, Issue issue) {
    final take = (widget.takeLabel ?? '').trim();
    final showSummary = widget.showSummary && issue.summary.isNotEmpty;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(issue.title, style: Theme.of(context).textTheme.titleLarge),
        if (take.isNotEmpty) ...[
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: TakeleyColors.accentSoft,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              '내 생각 · $take',
              style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                letterSpacing: -0.2,
                color: TakeleyColors.accent,
              ),
            ),
          ),
        ],
        if (showSummary) ...[
          const SizedBox(height: 8),
          Text(
            issue.summary,
            maxLines: widget.imageLayout == IssueCardImageLayout.trailing
                ? 2
                : 3,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ],
      ],
    );
  }

  String _footerMeta(Issue issue, String when) {
    final parts = <String>[];
    if (when.isNotEmpty) parts.add(when);
    final fmt = NumberFormat.decimalPattern('ko_KR');
    if (issue.openCount > 0) parts.add('조회 ${fmt.format(issue.openCount)}');
    if (issue.participationCount > 0) {
      parts.add('생각 ${fmt.format(issue.participationCount)}');
    }
    return parts.join(' · ');
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
