import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../theme/takeley_colors.dart';
import '../utils/resolve_image.dart';

/// Safe subset markdown — mirrors `frontend/src/lib/columnMarkdown.tsx`.
class ColumnMarkdownView extends StatelessWidget {
  const ColumnMarkdownView({
    super.key,
    required this.source,
    this.emptyText = '아직 칼럼 본문이 준비되지 않았어요.',
  });

  final String source;
  final String emptyText;

  static bool _isSafeUrl(String url) {
    final t = url.trim();
    if (t.isEmpty) return false;
    if (t.startsWith('/media/')) return true;
    final u = Uri.tryParse(t);
    if (u == null) return false;
    return u.scheme == 'http' || u.scheme == 'https';
  }

  @override
  Widget build(BuildContext context) {
    final text = source.trim();
    if (text.isEmpty) {
      return Text(
        emptyText,
        style: const TextStyle(
          fontSize: 16,
          height: 1.65,
          color: TakeleyColors.muted,
        ),
      );
    }

    final blocks = partitionColumnBlocks(text);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (var bi = 0; bi < blocks.length; bi++)
          ..._buildBlock(context, blocks[bi], bi),
      ],
    );
  }

  /// Heading / image lines become blocks even without blank lines around them.
  static List<String> partitionColumnBlocks(String source) {
    final lines = source.replaceAll('\r\n', '\n').split('\n');
    final out = <String>[];
    final buf = <String>[];
    void flush() {
      final t = buf.join('\n').trim();
      if (t.isNotEmpty) out.add(t);
      buf.clear();
    }

    final heading = RegExp(r'^#{1,3} ');
    final imgOnly = RegExp(r'^!\[[^\]]*\]\([^)]+\)$');
    for (final line in lines) {
      final trimmed = line.trim();
      if (heading.hasMatch(trimmed)) {
        flush();
        out.add(trimmed);
        continue;
      }
      if (imgOnly.hasMatch(trimmed)) {
        flush();
        out.add(trimmed);
        continue;
      }
      if (trimmed.isEmpty) {
        flush();
        continue;
      }
      buf.add(line);
    }
    flush();
    return out;
  }

  List<Widget> _buildBlock(BuildContext context, String block, int bi) {
    if (block.isEmpty) return const [];

    final imgOnly = RegExp(r'^!\[([^\]]*)\]\(([^)]+)\)$').firstMatch(block);
    if (imgOnly != null) {
      final src = imgOnly.group(2)!.trim();
      if (!_isSafeUrl(src)) return const [];
      final url = resolveImageUrl(src) ?? src;
      return [
        Padding(
          padding: const EdgeInsets.only(bottom: 16),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: CachedNetworkImage(
              imageUrl: url,
              fit: BoxFit.cover,
              errorWidget: (_, __, ___) => const SizedBox.shrink(),
            ),
          ),
        ),
      ];
    }

    if (block.startsWith('### ')) {
      return [
        Padding(
          padding: const EdgeInsets.only(top: 8, bottom: 10),
          child: Text.rich(
            TextSpan(
              children: _renderInline(block.substring(4), 'h-$bi'),
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w800,
                height: 1.35,
                letterSpacing: -0.3,
                color: TakeleyColors.fg,
              ),
            ),
          ),
        ),
      ];
    }

    if (block.startsWith('## ')) {
      return [
        Padding(
          padding: const EdgeInsets.only(top: 8, bottom: 10),
          child: Text.rich(
            TextSpan(
              children: _renderInline(block.substring(3), 'h-$bi'),
              style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w800,
                height: 1.35,
                letterSpacing: -0.3,
                color: TakeleyColors.fg,
              ),
            ),
          ),
        ),
      ];
    }

    if (block.startsWith('# ')) {
      return [
        Padding(
          padding: const EdgeInsets.only(top: 8, bottom: 10),
          child: Text.rich(
            TextSpan(
              children: _renderInline(block.substring(2), 'h-$bi'),
              style: const TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.w800,
                height: 1.3,
                letterSpacing: -0.35,
                color: TakeleyColors.fg,
              ),
            ),
          ),
        ),
      ];
    }

    final lines = block.split('\n');
    final spans = <InlineSpan>[];
    for (var li = 0; li < lines.length; li++) {
      if (li > 0) spans.add(const TextSpan(text: '\n'));
      spans.addAll(_renderInline(lines[li], 'p-$bi-$li'));
    }

    return [
      Padding(
        padding: const EdgeInsets.only(bottom: 14),
        child: Text.rich(
          TextSpan(
            children: spans,
            style: const TextStyle(
              fontSize: 17,
              height: 1.75,
              fontWeight: FontWeight.w400,
              letterSpacing: -0.2,
              color: TakeleyColors.fg,
            ),
          ),
        ),
      ),
    ];
  }

  List<InlineSpan> _renderInline(String text, String keyPrefix) {
    // ***bold+italic*** before **bold** before *italic*
    final re = RegExp(
      r'!\[([^\]]*)\]\(([^)]+)\)|\[([^\]]+)\]\(([^)]+)\)|\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|\*(.+?)\*',
    );
    final nodes = <InlineSpan>[];
    var last = 0;
    var i = 0;
    for (final m in re.allMatches(text)) {
      if (m.start > last) {
        nodes.add(TextSpan(text: text.substring(last, m.start)));
      }
      final k = '$keyPrefix-${i++}';
      if (m.group(1) != null && m.group(2) != null) {
        final src = m.group(2)!.trim();
        if (_isSafeUrl(src)) {
          final url = resolveImageUrl(src) ?? src;
          nodes.add(
            WidgetSpan(
              alignment: PlaceholderAlignment.middle,
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: CachedNetworkImage(
                    imageUrl: url,
                    width: 120,
                    fit: BoxFit.cover,
                    errorWidget: (_, __, ___) => const SizedBox.shrink(),
                  ),
                ),
              ),
            ),
          );
        } else {
          nodes.add(TextSpan(text: m.group(0)));
        }
      } else if (m.group(3) != null && m.group(4) != null) {
        final href = m.group(4)!.trim();
        final label = m.group(3)!;
        if (_isSafeUrl(href)) {
          nodes.add(
            TextSpan(
              text: label,
              style: const TextStyle(
                color: TakeleyColors.accent,
                fontWeight: FontWeight.w600,
                decoration: TextDecoration.underline,
                decorationColor: TakeleyColors.accent,
              ),
            ),
          );
        } else {
          nodes.add(TextSpan(text: label));
        }
      } else if (m.group(5) != null) {
        // ***bold+italic***
        nodes.add(
          TextSpan(
            style: const TextStyle(
              fontWeight: FontWeight.w700,
              fontStyle: FontStyle.italic,
              color: TakeleyColors.fg,
            ),
            children: _renderInline(m.group(5)!, '$k-bi'),
          ),
        );
      } else if (m.group(6) != null) {
        // **bold**
        nodes.add(
          TextSpan(
            style: const TextStyle(
              fontWeight: FontWeight.w700,
              color: TakeleyColors.fg,
            ),
            children: _renderInline(m.group(6)!, '$k-b'),
          ),
        );
      } else if (m.group(7) != null) {
        // *italic*
        nodes.add(
          TextSpan(
            style: const TextStyle(
              fontStyle: FontStyle.italic,
              color: TakeleyColors.fg,
            ),
            children: _renderInline(m.group(7)!, '$k-i'),
          ),
        );
      }
      last = m.end;
    }
    if (last < text.length) {
      nodes.add(TextSpan(text: text.substring(last)));
    }
    return nodes;
  }
}
