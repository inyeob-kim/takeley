"""1024 App Store icon: royal-blue field + TAKELEY slab T. Stdlib only."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "brand"
SIZE = 1024
SS = 2
MASTER = SIZE * SS
BLUE = (45, 91, 227, 255)
WHITE = (255, 255, 255, 255)
CLEAR = (0, 0, 0, 0)


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def _png(pixels: list[list[tuple[int, int, int, int]]]) -> bytes:
    height = len(pixels)
    width = len(pixels[0])
    raw = bytearray()
    for row in pixels:
        raw.append(0)
        for r, g, b, a in row:
            raw.extend((r, g, b, a))
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
            _chunk(b"IDAT", zlib.compress(bytes(raw), 9)),
            _chunk(b"IEND", b""),
        ]
    )


def _in_round_rect(x: float, y: float, x0: int, y0: int, x1: int, y1: int, r: int) -> bool:
    if x < x0 or x >= x1 or y < y0 or y >= y1:
        return False
    if r <= 0:
        return True
    cx0, cy0, cx1, cy1 = x0 + r, y0 + r, x1 - r, y1 - r
    if cx0 <= x < cx1 or cy0 <= y < cy1:
        return True
    if x < cx0 and y < cy0:
        return (x - cx0) ** 2 + (y - cy0) ** 2 <= r * r
    if x >= cx1 and y < cy0:
        return (x - cx1) ** 2 + (y - cy0) ** 2 <= r * r
    if x < cx0 and y >= cy1:
        return (x - cx0) ** 2 + (y - cy1) ** 2 <= r * r
    if x >= cx1 and y >= cy1:
        return (x - cx1) ** 2 + (y - cy1) ** 2 <= r * r
    return True


def _t_mask() -> list[list[bool]]:
    """Same T, ~10% tighter: heavier bar, slimmer stem, micro-radius terminals."""
    s = SS
    bar_h = 192 * s
    stem_w = 156 * s
    bar_w = 608 * s
    radius = 36 * s
    x0 = (MASTER - bar_w) // 2
    x1 = x0 + bar_w
    stem_x0 = (MASTER - stem_w) // 2
    stem_x1 = stem_x0 + stem_w
    top = 258 * s
    bottom = 742 * s
    mask = [[False] * MASTER for _ in range(MASTER)]
    for y in range(top, bottom):
        row = mask[y]
        for x in range(x0, x1):
            in_bar = _in_round_rect(x + 0.5, y + 0.5, x0, top, x1, top + bar_h, radius)
            in_stem = _in_round_rect(
                x + 0.5, y + 0.5, stem_x0, top, stem_x1, bottom, radius
            )
            if in_bar or in_stem:
                row[x] = True
    return mask


def _paint(
    fill: tuple[int, int, int, int],
    ink: tuple[int, int, int, int],
    mask: list[list[bool]],
) -> list[list[tuple[int, int, int, int]]]:
    out: list[list[tuple[int, int, int, int]]] = []
    for y in range(SIZE):
        row: list[tuple[int, int, int, int]] = []
        y0 = y * SS
        for x in range(SIZE):
            x0 = x * SS
            cover = 0
            for dy in range(SS):
                src = mask[y0 + dy]
                for dx in range(SS):
                    if src[x0 + dx]:
                        cover += 1
            if cover == 0:
                row.append(fill)
            elif cover == SS * SS:
                row.append(ink)
            else:
                t = cover / (SS * SS)
                row.append(
                    tuple(int(fill[i] + (ink[i] - fill[i]) * t) for i in range(4))  # type: ignore[misc]
                )
        out.append(row)
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    mask = _t_mask()
    (OUT / "app_icon.png").write_bytes(_png(_paint(BLUE, WHITE, mask)))
    (OUT / "app_icon_fg.png").write_bytes(_png(_paint(CLEAR, WHITE, mask)))
    print(f"wrote {OUT / 'app_icon.png'}")
    print(f"wrote {OUT / 'app_icon_fg.png'}")


if __name__ == "__main__":
    main()
