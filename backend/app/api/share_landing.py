"""Path-based Issue share landing: OG for messengers + readable page + app CTA."""

from __future__ import annotations

import html
import json
import re
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.db.models import Participation, Signal
from app.db.session import get_db

router = APIRouter(tags=["share"])

_WS_RE = re.compile(r"\s+")
_IMG_ONLY_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")
_IMG_INLINE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")

_CATEGORY_KO = {
    "macro": "경제",
    "economy": "경제",
    "tech": "테크",
    "market": "시장",
    "policy": "정책",
    "company": "기업",
    "crypto": "크립토",
    "energy": "에너지",
    "geopolitics": "국제",
}


def _abs_url(origin: str, path_or_url: str | None) -> str | None:
    if not path_or_url:
        return None
    text = path_or_url.strip()
    if not text:
        return None
    if re.match(r"^https?://", text, re.I):
        return text
    base = origin.rstrip("/")
    if not text.startswith("/"):
        text = f"/{text}"
    return f"{base}{text}"


def _truncate(text: str, max_len: int) -> str:
    cleaned = _WS_RE.sub(" ", (text or "").strip())
    if len(cleaned) <= max_len:
        return cleaned
    return f"{cleaned[: max_len - 1].rstrip()}…"


def _category_label(raw: str) -> str:
    key = (raw or "").strip().lower()
    if not key:
        return ""
    return _CATEGORY_KO.get(key, raw.strip())


def _safe_href(url: str, origin: str) -> str | None:
    text = (url or "").strip()
    if not text:
        return None
    if text.startswith("/media/"):
        return _abs_url(origin, text)
    if re.match(r"^https?://", text, re.I):
        return text
    if text.startswith("/"):
        return _abs_url(origin, text)
    return None


def _format_inline(text: str, origin: str) -> str:
    """Escape then restore a safe subset of markdown inline tokens."""
    placeholders: list[str] = []

    def _ph(html_chunk: str) -> str:
        placeholders.append(html_chunk)
        return f"\x00PH{len(placeholders) - 1}\x00"

    def _sub_img(m: re.Match[str]) -> str:
        href = _safe_href(m.group(2), origin)
        if not href:
            return ""
        alt = html.escape(m.group(1) or "", quote=True)
        return _ph(
            f'<img class="inline-img" src="{html.escape(href, quote=True)}" alt="{alt}" />'
        )

    def _sub_link(m: re.Match[str]) -> str:
        href = _safe_href(m.group(2), origin)
        label = html.escape(m.group(1) or "")
        if not href:
            return label
        return _ph(
            f'<a href="{html.escape(href, quote=True)}" rel="noopener noreferrer" '
            f'target="_blank">{label}</a>'
        )

    work = _IMG_INLINE_RE.sub(_sub_img, text)
    work = _LINK_RE.sub(_sub_link, work)
    work = html.escape(work)
    work = _BOLD_RE.sub(r"<strong>\1</strong>", work)
    work = _ITALIC_RE.sub(r"<em>\1</em>", work)
    work = work.replace("\n", "<br />")
    for i, chunk in enumerate(placeholders):
        work = work.replace(f"\x00PH{i}\x00", chunk)
    return work


def _partition_column_blocks(text: str) -> list[str]:
    """Heading / image lines become blocks even without blank lines around them."""
    lines = text.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        t = "\n".join(buf).strip()
        if t:
            out.append(t)
        buf.clear()

    for line in lines:
        trimmed = line.strip()
        if re.match(r"^#{1,3} ", trimmed):
            flush()
            out.append(trimmed)
            continue
        if _IMG_ONLY_RE.match(trimmed):
            flush()
            out.append(trimmed)
            continue
        if trimmed == "":
            flush()
            continue
        buf.append(line)
    flush()
    return out


def _render_column_html(raw: str, origin: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    parts: list[str] = []
    for block in _partition_column_blocks(text):
        img = _IMG_ONLY_RE.match(block)
        if img:
            href = _safe_href(img.group(2), origin)
            if not href:
                continue
            alt = html.escape(img.group(1) or "", quote=True)
            parts.append(
                f'<img class="body-img" src="{html.escape(href, quote=True)}" alt="{alt}" />'
            )
            continue
        if block.startswith("### "):
            parts.append(f"<h3>{_format_inline(block[4:], origin)}</h3>")
            continue
        if block.startswith("## "):
            parts.append(f"<h2>{_format_inline(block[3:], origin)}</h2>")
            continue
        if block.startswith("# "):
            parts.append(f"<h2>{_format_inline(block[2:], origin)}</h2>")
            continue
        parts.append(f"<p>{_format_inline(block, origin)}</p>")
    if not parts:
        return ""
    return f'<div class="column">{"".join(parts)}</div>'


def _column_source(row: Signal) -> str:
    column = (getattr(row, "column_body", None) or "").strip()
    if column:
        return column
    why = (row.why_it_matters or "").strip()
    summary = (row.summary or "").strip()
    if why and why != summary:
        return why
    return ""


def _app_scheme_url(
    issue_id: str,
    *,
    sid: str | None,
    ref: str | None,
) -> str:
    q: dict[str, str] = {}
    if sid:
        q["sid"] = sid
    if ref:
        q["ref"] = ref
    qs = f"?{urlencode(q)}" if q else ""
    return f"takeley://i/{quote(issue_id, safe='')}{qs}"


def _option_counts(db: Session, signal_id: str) -> dict[str, int]:
    rows = (
        db.query(Participation.option_id, func.count(Participation.id))
        .filter(Participation.signal_id == signal_id)
        .group_by(Participation.option_id)
        .all()
    )
    return {oid: int(n) for oid, n in rows}


def _format_count_ko(n: int) -> str:
    return f"{n:,}"


def _teaser_html(
    row: Signal,
    *,
    counts: dict[str, int],
    total: int,
) -> tuple[str, str]:
    """Return (teaser_html, sticky_cta_label).

    Option labels stay readable. Real vote % / bar lengths are never shown on
    the landing — uniform deco only — so winners do not leak before the app.
    """
    esc = html.escape
    suitable = bool(getattr(row, "participation_suitable", False))
    options = sorted(
        row.participation_options or [],
        key=lambda o: (o.display_order, o.created_at or 0),
    )
    question = (
        (getattr(row, "participation_question", None) or "").strip()
        or "당신의 생각은?"
    )

    # Social proof: interest / debate — not who is winning.
    proof_bits: list[str] = []
    if total > 0:
        proof_bits.append("지금 의견이 갈리고 있어요")
    open_count = int(getattr(row, "open_count", 0) or 0)
    if open_count >= 10:
        proof_bits.append(f"{_format_count_ko(open_count)}명이 봤어요")
    proof = " · ".join(proof_bits)

    if suitable and options:
        # counts/total reserved for future; never leak ranking on web teaser.
        _ = counts
        rows_html: list[str] = []
        for o in options:
            rows_html.append(
                f"""<button type="button" class="teaser-opt js-vote" data-option-id="{esc(o.id, quote=True)}">
  <span class="teaser-opt__label">{esc(o.label)}</span>
  <span class="teaser-opt__bar" aria-hidden="true">
    <span class="teaser-opt__fill"></span>
  </span>
  <span class="teaser-opt__pct" aria-hidden="true">??</span>
</button>"""
            )
        proof_html = (
            f'<p class="teaser-proof">{esc(proof)}</p>' if proof else ""
        )
        teaser = f"""
<section class="teaser" id="teaser" aria-label="다른 사람 생각">
  <p class="teaser-kicker">다른 사람 생각</p>
  <p class="teaser-q">{esc(question)}</p>
  {proof_html}
  <div class="teaser-opts">
    {"".join(rows_html)}
  </div>
  <button type="button" class="teaser-confirm js-confirm-vote" hidden>결과 보기</button>
  <p class="teaser-lock">선택한 뒤에 다른 사람 생각을 볼 수 있어요.</p>
  <p class="voted-note" hidden>내 생각을 남겼어요.</p>
  <div class="web-share" id="web-share" hidden>
    <button type="button" class="web-share__btn js-share" data-share-mode="issue_only">이 이슈, 너는 어떻게 생각해?</button>
  </div>
</section>
"""
        return teaser, "이 이슈, 어떻게 생각해?"

    proof_html = f'<p class="teaser-proof">{esc(proof)}</p>' if proof else ""
    teaser = f"""
<section class="teaser teaser--soft" aria-label="앱에서 이어보기">
  <p class="teaser-kicker">TAKELEY</p>
  <p class="teaser-q">생각 남기기 · 댓글은 앱에서</p>
  {proof_html}
  <p class="teaser-lock">앱에서 이어서 보고 의견을 남겨 보세요</p>
</section>
"""
    return teaser, "앱에서 이어서 보기"


@router.api_route("/i/{issue_id}", methods=["GET", "HEAD"], response_class=HTMLResponse)
def issue_share_landing(
    issue_id: str,
    sid: str | None = Query(None),
    ref: str | None = Query(None),
    take: str | None = Query(None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    settings = get_settings()
    share_origin = (settings.public_share_origin or "http://127.0.0.1:8000").rstrip(
        "/"
    )
    android_store = (settings.public_android_store_url or "").strip()
    ios_store = (settings.public_ios_store_url or "").strip()

    row = (
        db.query(Signal)
        .options(joinedload(Signal.participation_options))
        .filter(Signal.id == issue_id, Signal.status == "published")
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Issue not found")

    title = _truncate(row.title or "TAKELEY", 80)
    summary_full = _truncate(
        row.summary or row.why_it_matters or title,
        400,
    )
    take_label = _truncate((take or "").strip(), 40)
    if take_label:
        description = _truncate(
            f"나는 ‘{take_label}’에 한 표 했어. 너는 어떻게 생각해?",
            160,
        )
    else:
        description = _truncate(summary_full, 160)
    category = _category_label(getattr(row, "category", None) or "")

    canonical = f"{share_origin}/i/{quote(issue_id, safe='')}"
    q: dict[str, str] = {}
    if sid:
        q["sid"] = sid
    if ref:
        q["ref"] = ref
    if take_label:
        q["take"] = take_label
    if q:
        canonical = f"{canonical}?{urlencode(q)}"

    issue_image = _abs_url(share_origin, getattr(row, "image_url", None))
    image = issue_image or f"{share_origin}/static/og-default.png?v=td"

    app_url = _app_scheme_url(issue_id, sid=sid, ref=ref)
    column_raw = _column_source(row)
    column_html = _render_column_html(column_raw, share_origin)
    counts = _option_counts(db, row.id)
    total = sum(counts.values())
    teaser_html, cta_label = _teaser_html(row, counts=counts, total=total)
    esc = html.escape

    category_html = (
        f'<p class="cat">{esc(category)}</p>' if category else ""
    )
    cover_html = (
        f'<img class="cover" src="{esc(issue_image, quote=True)}" alt="" />'
        if issue_image
        else ""
    )
    author = (getattr(row, "column_author_name", None) or "").strip()
    author_html = (
        f'<p class="column-author">{esc(author)}</p>' if author and column_html else ""
    )
    collapsed = " is-collapsed" if column_html and len(column_raw) > 280 else ""
    more_html = (
        '<button type="button" class="column-more" id="column-more">전체 칼럼 읽기</button>'
        if collapsed
        else ""
    )
    if column_html:
        body_section = (
            f'<section class="column-block{collapsed}" id="column-block">'
            f"{author_html}{column_html}{more_html}</section>"
        )
    else:
        body_section = '<p class="column-empty">본문이 아직 준비되지 않았어요.</p>'

    store_links: list[str] = []
    if android_store:
        store_links.append(
            f'<a class="store" data-platform="android" href="{esc(android_store, quote=True)}">'
            "Google Play에서 설치</a>"
        )
    if ios_store:
        store_links.append(
            f'<a class="store" data-platform="ios" href="{esc(ios_store, quote=True)}">'
            "App Store에서 설치</a>"
        )
    if not store_links:
        store_links.append(
            '<p class="store-msg">앱 스토어 링크는 곧 연결됩니다. '
            "지금은 앱이 설치돼 있다면 위 버튼으로 열어 주세요.</p>"
        )
    store_html = "\n      ".join(store_links)

    page = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{esc(f"TAKELEY · {title}")}</title>
  <meta name="description" content="{esc(description, quote=True)}" />
  <link rel="canonical" href="{esc(canonical, quote=True)}" />
  <meta property="og:type" content="article" />
  <meta property="og:site_name" content="TAKELEY" />
  <meta property="og:title" content="{esc(title, quote=True)}" />
  <meta property="og:description" content="{esc(description, quote=True)}" />
  <meta property="og:url" content="{esc(canonical, quote=True)}" />
  <meta property="og:image" content="{esc(image, quote=True)}" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{esc(title, quote=True)}" />
  <meta name="twitter:description" content="{esc(description, quote=True)}" />
  <meta name="twitter:image" content="{esc(image, quote=True)}" />
  <style>
    :root {{
      --accent: #2D5BE3;
      --fg: #0A0A0A;
      --muted: #6B7280;
      --soft: #F7F8FA;
      --border: rgba(0,0,0,0.08);
      --phone: 26.25rem; /* 420px — between common 390 and Max ~428 */
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Pretendard", "Apple SD Gothic Neo", system-ui, -apple-system, sans-serif;
      color: var(--fg);
      background: #EEF0F3;
      line-height: 1.5;
    }}
    .shell {{
      max-width: var(--phone);
      margin: 0 auto;
      min-height: 100vh;
      background: #fff;
      box-shadow: 0 0 0 1px var(--border);
    }}
    .topbar {{
      position: sticky;
      top: 0;
      z-index: 5;
      background: rgba(255,255,255,0.96);
      backdrop-filter: blur(8px);
      border-bottom: 1px solid var(--border);
    }}
    .topbar-inner {{
      padding: 0.85rem 1.25rem;
    }}
    .brand {{
      margin: 0;
      font-size: 0.8125rem;
      font-weight: 700;
      letter-spacing: 0.04em;
      color: var(--accent);
    }}
    .wrap {{
      padding: 1.25rem 1.25rem 9rem;
    }}
    .cat {{
      margin: 0 0 0.5rem;
      font-size: 0.6875rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      color: var(--accent);
      text-transform: uppercase;
    }}
    h1 {{
      margin: 0 0 0.75rem;
      font-size: 1.625rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      line-height: 1.25;
    }}
    .summary {{
      margin: 0 0 1.25rem;
      font-size: 1.0625rem;
      color: var(--muted);
      line-height: 1.55;
    }}
    .cover {{
      display: block;
      width: 100%;
      max-height: 14rem;
      object-fit: cover;
      border-radius: 0.75rem;
      margin-bottom: 1.5rem;
      background: var(--soft);
    }}
    .column {{
      font-size: 1.0625rem;
      line-height: 1.7;
      color: var(--fg);
    }}
    .column p {{ margin: 0 0 1.1rem; }}
    .column h2, .column h3 {{
      margin: 1.4rem 0 0.65rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      line-height: 1.3;
    }}
    .column h2 {{ font-size: 1.25rem; }}
    .column h3 {{ font-size: 1.1rem; }}
    .column a {{
      color: var(--accent);
      text-decoration: underline;
      text-underline-offset: 2px;
    }}
    .body-img, .inline-img {{
      display: block;
      width: 100%;
      border-radius: 0.75rem;
      margin: 0 0 1.1rem;
      background: var(--soft);
    }}
    .column-empty {{
      margin: 0;
      color: var(--muted);
      font-size: 0.9375rem;
    }}
    .teaser {{
      margin: 2rem 0 0;
      padding: 1.25rem 1rem 1.1rem;
      border: 1px solid var(--border);
      border-radius: 0.75rem;
      background: var(--soft);
    }}
    .teaser-kicker {{
      margin: 0 0 0.35rem;
      font-size: 0.6875rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      color: var(--accent);
      text-transform: uppercase;
    }}
    .teaser-q {{
      margin: 0 0 0.5rem;
      font-size: 1.125rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      line-height: 1.3;
    }}
    .teaser-proof {{
      margin: 0 0 0.9rem;
      font-size: 0.8125rem;
      color: var(--muted);
    }}
    .teaser-opts {{
      display: flex;
      flex-direction: column;
      gap: 0.55rem;
    }}
    .teaser-opt {{
      display: grid;
      grid-template-columns: 1fr auto;
      grid-template-rows: auto auto;
      gap: 0.35rem 0.75rem;
      width: 100%;
      text-align: left;
      padding: 0.75rem 0.85rem;
      border: 1px solid var(--border);
      border-radius: 0.65rem;
      background: #fff;
      cursor: pointer;
      font-family: inherit;
      color: inherit;
    }}
    .teaser-opt:active {{ opacity: 0.9; }}
    .teaser-opt__label {{
      grid-column: 1;
      font-size: 0.9375rem;
      font-weight: 600;
    }}
    .teaser:not(.is-voted) .teaser-opt__bar,
    .teaser:not(.is-voted) .teaser-opt__pct {{
      display: none;
    }}
    .teaser-opt__pct {{
      grid-column: 2;
      grid-row: 1 / span 2;
      align-self: center;
      font-size: 0.875rem;
      font-weight: 700;
      letter-spacing: 0.04em;
      color: var(--accent);
      user-select: none;
      pointer-events: none;
    }}
    .teaser-opt__bar {{
      grid-column: 1;
      height: 6px;
      border-radius: 999px;
      background: rgba(0,0,0,0.06);
      overflow: hidden;
      user-select: none;
      pointer-events: none;
    }}
    .teaser-opt__fill {{
      display: block;
      width: 38%;
      height: 100%;
      background: rgba(45, 91, 227, 0.45);
      border-radius: 999px;
    }}
    .teaser-lock {{
      margin: 0.85rem 0 0;
      font-size: 0.8125rem;
      color: var(--muted);
      text-align: center;
    }}
    .teaser-opt.is-pending,
    .teaser-opt.is-mine {{
      border-color: var(--accent);
      background: #E8EEFC;
    }}
    .teaser.is-voted .teaser-opt {{
      cursor: default;
    }}
    .teaser-confirm {{
      display: flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      margin-top: 0.85rem;
      min-height: 52px;
      border: none;
      border-radius: 999px;
      background: #2D5BE3;
      color: #fff;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      box-shadow: 4px 4px 0 #0A0A0A;
    }}
    .teaser-confirm[hidden] {{ display: none; }}
    .teaser-confirm:active {{
      transform: translate(2px, 2px);
      box-shadow: 2px 2px 0 #0A0A0A;
    }}
    .voted-note {{
      margin: 0.85rem 0 0;
      font-size: 0.9375rem;
      font-weight: 700;
    }}
    .web-share {{
      display: flex;
      flex-direction: column;
      gap: 0.35rem;
      margin-top: 0.75rem;
    }}
    .web-share__btn {{
      background: transparent;
      border: none;
      color: var(--accent);
      font: inherit;
      font-size: 0.875rem;
      font-weight: 600;
      text-align: center;
      cursor: pointer;
      padding: 0.35rem;
    }}
    .column-block {{ margin-top: 2rem; }}
    .column-block.is-collapsed .column {{
      max-height: 12rem;
      overflow: hidden;
    }}
    .column-author {{
      margin: 0 0 0.65rem;
      font-size: 0.875rem;
      font-weight: 700;
      color: var(--muted);
    }}
    .column-more {{
      display: block;
      margin: 0.25rem 0 0;
      padding: 0;
      border: none;
      background: transparent;
      color: var(--accent);
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }}
    .column-more[hidden] {{ display: none; }}
    .footer {{
      position: fixed;
      left: 50%;
      transform: translateX(-50%);
      width: 100%;
      max-width: var(--phone);
      bottom: 0;
      padding: 0.875rem 1.25rem calc(0.875rem + env(safe-area-inset-bottom));
      background: rgba(255,255,255,0.96);
      border-top: 1px solid var(--border);
      backdrop-filter: blur(8px);
    }}
    .footer-inner {{
      display: flex;
      flex-direction: column;
      gap: 0.55rem;
      padding-right: 4px;
      padding-bottom: 4px;
    }}
    .cta {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      text-align: center;
      text-decoration: none;
      background: #2D5BE3;
      color: #fff;
      font-weight: 700;
      font-size: 16px;
      letter-spacing: -0.02em;
      min-height: 52px;
      padding: 0.85rem 1.25rem;
      border-radius: 999px;
      border: none;
      cursor: pointer;
      width: 100%;
      font-family: inherit;
      box-shadow: 4px 4px 0 #0A0A0A;
      transition: transform 80ms ease, box-shadow 80ms ease;
    }}
    .cta:active {{
      transform: translate(2px, 2px);
      box-shadow: 2px 2px 0 #0A0A0A;
    }}
    .store-panel {{
      display: none;
      flex-direction: column;
      gap: 0.4rem;
      margin-top: 0.25rem;
    }}
    .store-panel.is-open {{ display: flex; }}
    .store {{
      text-align: center;
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--accent);
      text-decoration: none;
      padding: 0.5rem;
    }}
    .store-msg {{
      margin: 0;
      text-align: center;
      font-size: 0.8125rem;
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <div class="shell">
  <header class="topbar">
    <div class="topbar-inner">
      <p class="brand">TAKELEY</p>
    </div>
  </header>
  <div class="wrap">
    {category_html}
    <h1>{esc(title)}</h1>
    <p class="summary">{esc(summary_full)}</p>
    {cover_html}
    {teaser_html}
    {body_section}
  </div>
  <div class="footer">
    <div class="footer-inner">
      <button type="button" class="cta js-open-app">{esc(cta_label)}</button>
      <div class="store-panel" id="store-panel" hidden>
        <p class="store-msg">앱이 없다면 설치해 주세요</p>
        {store_html}
      </div>
    </div>
  </div>
  </div>
  <script>
    (function () {{
      var appUrl = {json.dumps(app_url)};
      var androidStore = {json.dumps(android_store)};
      var iosStore = {json.dumps(ios_store)};
      var issueId = {json.dumps(issue_id)};
      var shareId = {json.dumps(sid or "")};
      var refUserId = {json.dumps(ref or "")};
      var issueTitle = {json.dumps(title)};
      var shareUrl = {json.dumps(f"{share_origin}/i/{quote(issue_id, safe='')}")};
      var panel = document.getElementById("store-panel");
      var teaser = document.getElementById("teaser");
      var timer = null;
      var myLabel = "";
      var pendingId = "";
      var voting = false;

      function isIOS() {{
        return /iPad|iPhone|iPod/.test(navigator.userAgent) ||
          (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
      }}
      function isAndroid() {{
        return /Android/i.test(navigator.userAgent);
      }}
      function showStore() {{
        if (!panel) return;
        panel.hidden = false;
        panel.classList.add("is-open");
        var links = panel.querySelectorAll("a.store[data-platform]");
        links.forEach(function (a) {{
          var p = a.getAttribute("data-platform");
          if (p === "ios" && !isIOS() && androidStore) a.style.display = "none";
          if (p === "android" && !isAndroid() && iosStore) a.style.display = "none";
        }});
      }}
      function openApp() {{
        if (timer) clearTimeout(timer);
        var start = Date.now();
        timer = setTimeout(function () {{
          if (document.visibilityState === "visible" && Date.now() - start >= 1400) {{
            showStore();
          }}
        }}, 1600);
        window.location.href = appUrl;
      }}
      document.addEventListener("visibilitychange", function () {{
        if (document.visibilityState === "hidden" && timer) {{
          clearTimeout(timer);
          timer = null;
        }}
      }});
      document.querySelectorAll(".js-open-app").forEach(function (el) {{
        el.addEventListener("click", openApp);
      }});

      function postEvent(name, intent) {{
        return ensureUser().then(function (userId) {{
          if (!userId) return;
          var body = {{ event: name, user_id: userId }};
          if (shareId) body.share_id = shareId;
          if (refUserId) body.ref_user_id = refUserId;
          if (intent) body.share_intent = intent;
          return fetch("/api/v1/issues/" + encodeURIComponent(issueId) + "/events", {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify(body)
          }});
        }});
      }}
      function ensureUser() {{
        var deviceKey = "takeley_web_device_id";
        var userKey = "takeley_web_user_id";
        var deviceId = localStorage.getItem(deviceKey);
        var userId = localStorage.getItem(userKey);
        if (userId && deviceId && deviceId.length >= 8) return Promise.resolve(userId);
        if (!deviceId || deviceId.length < 8) {{
          deviceId = "web-" + (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()));
          localStorage.setItem(deviceKey, deviceId);
        }}
        return fetch("/api/v1/devices/register", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ device_id: deviceId, platform: "web" }})
        }}).then(function (res) {{
          if (!res.ok) return "";
          return res.json();
        }}).then(function (data) {{
          var id = data && data.user && data.user.id;
          if (!id) return "";
          localStorage.setItem(userKey, id);
          return id;
        }}).catch(function () {{ return ""; }});
      }}
      function reveal(options, myId) {{
        if (!teaser || !options) return;
        var total = 0;
        options.forEach(function (o) {{ total += Number(o.count) || 0; }});
        teaser.classList.add("is-voted");
        var note = teaser.querySelector(".voted-note");
        var lock = teaser.querySelector(".teaser-lock");
        var confirm = teaser.querySelector(".js-confirm-vote");
        if (confirm) confirm.hidden = true;
        if (lock) lock.hidden = true;
        teaser.querySelectorAll(".js-vote").forEach(function (btn) {{
          var id = btn.getAttribute("data-option-id");
          var match = null;
          options.forEach(function (o) {{ if (o.id === id) match = o; }});
          if (!match) return;
          var count = Number(match.count) || 0;
          var pct = total > 0 ? Math.round((count / total) * 100) : 0;
          var pctEl = btn.querySelector(".teaser-opt__pct");
          var fill = btn.querySelector(".teaser-opt__fill");
          if (pctEl) pctEl.textContent = pct + "%";
          if (fill) fill.style.width = pct + "%";
          btn.classList.toggle("is-mine", id === myId);
          if (id === myId) myLabel = ((btn.querySelector(".teaser-opt__label") || {{}}).textContent || "").trim();
        }});
        if (note && myLabel) {{
          note.textContent = "‘" + myLabel + "’를 선택했어요. 선택은 바꿀 수 없어요.";
          note.hidden = false;
        }} else if (note) {{
          note.hidden = false;
        }}
        var shareBox = document.getElementById("web-share");
        if (shareBox && navigator.share) shareBox.hidden = false;
      }}
      function vote(optionId) {{
        if (voting || !optionId) return;
        if (teaser && teaser.classList.contains("is-voted")) return;
        voting = true;
        function voteFailed() {{
          var lock = teaser && teaser.querySelector(".teaser-lock");
          if (lock) lock.textContent = "지금은 앱에서 의견을 남겨 주세요";
        }}
        ensureUser().then(function (userId) {{
          if (!userId) {{ voteFailed(); voting = false; return; }}
          return fetch("/api/v1/issues/" + encodeURIComponent(issueId) + "/participate", {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify({{ option_id: optionId, user_id: userId }})
          }}).then(function (res) {{
            if (!res.ok) return null;
            return res.json();
          }}).then(function (data) {{
            if (data && data.options) {{
              reveal(data.options, data.my_option_id || optionId);
              return;
            }}
            voteFailed();
          }}).finally(function () {{ voting = false; }});
        }});
      }}
      document.querySelectorAll(".js-vote").forEach(function (btn) {{
        btn.addEventListener("click", function () {{
          if (!teaser || teaser.classList.contains("is-voted") || voting) return;
          pendingId = btn.getAttribute("data-option-id") || "";
          teaser.querySelectorAll(".js-vote").forEach(function (el) {{
            el.classList.toggle("is-pending", el === btn);
          }});
          var confirm = teaser.querySelector(".js-confirm-vote");
          if (confirm) confirm.hidden = false;
          var lock = teaser.querySelector(".teaser-lock");
          if (lock) lock.textContent = "다른 선택지를 누르면 바꿀 수 있어요.";
        }});
      }});
      var confirmVote = document.querySelector(".js-confirm-vote");
      if (confirmVote) {{
        confirmVote.addEventListener("click", function () {{
          if (pendingId) vote(pendingId);
        }});
      }}
      document.querySelectorAll(".js-share").forEach(function (btn) {{
        btn.addEventListener("click", function () {{
          var mode = btn.getAttribute("data-share-mode") || "issue_only";
          postEvent("share_clicked", mode);
          if (!navigator.share) return;
          navigator.share({{ url: shareUrl }}).catch(function (err) {{
            if (err && err.name === "AbortError") postEvent("share_cancelled", mode);
          }});
        }});
      }});
      document.querySelectorAll("a.store").forEach(function (a) {{
        a.addEventListener("click", function () {{
          if (a.getAttribute("href")) postEvent("store_click", "");
        }});
      }});
      var more = document.getElementById("column-more");
      if (more) {{
        more.addEventListener("click", function () {{
          var block = document.getElementById("column-block");
          if (block) block.classList.remove("is-collapsed");
          more.remove();
        }});
      }}
      ensureUser().then(function (userId) {{
        if (!userId) return;
        if (shareId) {{
          var key = "share_open:" + issueId + ":" + shareId;
          if (!sessionStorage.getItem(key)) {{
            sessionStorage.setItem(key, "1");
            postEvent("shared_link_opened", "");
          }}
        }}
        return fetch("/api/v1/issues/" + encodeURIComponent(issueId) + "?user_id=" + encodeURIComponent(userId))
          .then(function (res) {{ return res.ok ? res.json() : null; }})
          .then(function (data) {{
            if (data && data.my_option_id && data.options) reveal(data.options, data.my_option_id);
          }});
      }});
    }})();
  </script>
</body>
</html>
"""
    return HTMLResponse(content=page, status_code=200)
