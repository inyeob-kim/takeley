"""Official site HTML. Reading stays on /issues/{id}. /i/{id} remains the mobile share card."""

from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas import IssueOut
from app.api.share_landing import _render_column_html
from app.services.site_service import ColumnCard, SiteService, TakeCard

router = APIRouter(tags=["site"])

_WS = re.compile(r"\s+")
_MD_IMG = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MD_MARK = re.compile(r"[#*`_]+")
_KST = timezone(timedelta(hours=9))
_LOGO = "/static/favicon.png"
_SPLASH = "/static/og-splash.png"
_IOS_STORE = "https://apps.apple.com/kr/app/takeley/id6815212932"


def site_origin() -> str:
    """Canonical host is the apex site, even when share links use the API host."""
    origin = (get_settings().public_share_origin or "http://127.0.0.1:8000").rstrip("/")
    return origin.replace("://api.", "://", 1)


def _esc(value: str) -> str:
    return html.escape(value or "", quote=True)


def _ios_store_url() -> str:
    configured = (get_settings().public_ios_store_url or "").strip()
    return configured or _IOS_STORE


def _plain(text: str, limit: int) -> str:
    cleaned = _MD_IMG.sub("", text or "")
    cleaned = _MD_LINK.sub(r"\1", cleaned)
    cleaned = _MD_MARK.sub("", cleaned)
    cleaned = _WS.sub(" ", cleaned).strip()
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 1].rstrip()}…"


def _when(value: datetime | None) -> str:
    if not value:
        return ""
    aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(_KST).strftime("%Y-%m-%d")


def _trend(status: str | None) -> str:
    if status == "TRENDING":
        return "트렌딩"
    if status == "RISING":
        return "급상승"
    return ""


def _abs_media(url: str | None) -> str:
    text = (url or "").strip()
    if not text:
        return ""
    if text.startswith("http://") or text.startswith("https://"):
        return text
    if not text.startswith("/"):
        text = f"/{text}"
    return text


def _page(
    *,
    title: str,
    description: str,
    path: str,
    body: str,
    image: str | None = None,
    og_title: str | None = None,
    image_width: int | None = None,
    image_height: int | None = None,
) -> HTMLResponse:
    origin = site_origin()
    canonical = f"{origin}{path}"
    desc = _plain(description, 160)
    share_title = og_title or title
    og_image = image or _LOGO
    if og_image.startswith("/"):
        og_image = f"{origin}{og_image}"
    size_meta = ""
    if image_width and image_height:
        size_meta = (
            f'\n  <meta property="og:image:width" content="{image_width}" />'
            f'\n  <meta property="og:image:height" content="{image_height}" />'
        )
    store = _esc(_ios_store_url())
    doc = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="icon" type="image/png" href="/static/favicon.png" />
  <link rel="apple-touch-icon" href="/static/favicon.png" />
  <title>{_esc(title)}</title>
  <meta name="description" content="{_esc(desc)}" />
  <link rel="canonical" href="{_esc(canonical)}" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="TAKELEY" />
  <meta property="og:title" content="{_esc(share_title)}" />
  <meta property="og:description" content="{_esc(desc)}" />
  <meta property="og:url" content="{_esc(canonical)}" />
  <meta property="og:image" content="{_esc(og_image)}" />{size_meta}
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{_esc(share_title)}" />
  <meta name="twitter:description" content="{_esc(desc)}" />
  <meta name="twitter:image" content="{_esc(og_image)}" />
  <style>{_CSS}</style>
  <script>
    (function () {{
      if (location.hash) return;
      try {{
        var nav = performance.getEntriesByType("navigation")[0];
        if (nav && nav.type === "back_forward") return;
      }} catch (e) {{}}
      if ("scrollRestoration" in history) history.scrollRestoration = "manual";
      function pin() {{ if (!location.hash) window.scrollTo(0, 0); }}
      pin();
      document.addEventListener("DOMContentLoaded", pin);
      window.addEventListener("load", pin);
      window.addEventListener("pageshow", function (e) {{ if (!e.persisted) pin(); }});
    }})();
  </script>
</head>
<body>
  <div class="shell">
    {_header()}
    {body}
    {_footer()}
  </div>
  <a class="app-qr" href="{store}" aria-label="모바일 앱 받기">
    <img src="/static/app-qr.svg" alt="" width="68" height="68" />
    <span>모바일 앱 받기</span>
  </a>
</body>
</html>
"""
    return HTMLResponse(doc)


def _header() -> str:
    return """
    <header class="top">
      <a class="logo" href="/">TAKELEY</a>
      <nav class="nav">
        <a href="/issues">이슈</a>
        <a href="/columns">칼럼</a>
      </nav>
      <form class="search" action="/issues" method="get">
        <input type="search" name="q" maxlength="40" placeholder="이슈를 찾아보세요" aria-label="이슈 검색" />
      </form>
    </header>
    """


def _footer() -> str:
    return """
    <footer class="foot">
      <div>
        <p class="logo">TAKELEY</p>
        <p>Take a look. Take a side.</p>
      </div>
      <nav>
        <a href="/about">테이클리</a>
        <a href="/issues">이슈</a>
        <a href="/columns">칼럼</a>
        <a href="/privacy">개인정보</a>
        <a href="/terms">이용약관</a>
        <a href="/support">고객지원</a>
        <a href="mailto:hello@takeley.co">hello@takeley.co</a>
      </nav>
    </footer>
    """


def _photo(url: str | None) -> str | None:
    src = _abs_media(url)
    if not src:
        return None
    return f'<img src="{_esc(src)}" alt="" />'


def _issue_href(issue_id: str) -> str:
    return f"/issues/{quote(issue_id, safe='')}"


def _hero(issue: IssueOut) -> str:
    photo = _photo(issue.image_url)
    media = f'<div class="hero-media">{photo}</div>' if photo else ""
    trend = _trend(issue.trend_status)
    trend_html = f'<span class="badge">{_esc(trend)}</span>' if trend else ""
    cat = (issue.category or "").strip()
    cat_html = f'<p class="kicker">{_esc(cat)}</p>' if cat else ""
    question = (issue.participation_question or "").strip()
    ask = question or "이 이슈, 어떻게 생각해?"
    plain = "" if photo else " hero-plain"
    return f"""
    <a class="hero{plain}" href="{_esc(_issue_href(issue.id))}">
      {media}
      <div class="hero-copy">
        {cat_html}
        {trend_html}
        <h1>{_esc(issue.title)}</h1>
        <p>{_esc(_plain(issue.summary or issue.why_it_matters, 180))}</p>
        <span class="hero-ask">{_esc(ask)}</span>
      </div>
    </a>
    """


def _issue_row(issue: IssueOut, *, logo_fallback: bool = False) -> str:
    photo = _photo(issue.image_url)
    if photo:
        thumb = photo
        row_class = "row"
    elif logo_fallback:
        thumb = f'<img class="is-logo" src="{_SPLASH}" alt="" />'
        row_class = "row"
    else:
        thumb = ""
        row_class = "row row-text"
    cat = (issue.category or "").strip()
    meta = " · ".join(
        part
        for part in (cat, _when(issue.published_at), _trend(issue.trend_status))
        if part
    )
    ask = ""
    if issue.participation_suitable:
        ask = '<span class="ask">생각 남기기</span>'
    return f"""
    <a class="{row_class}" href="{_esc(_issue_href(issue.id))}">
      {thumb}
      <span>
        <strong>{_esc(issue.title)}</strong>
        <em>{_esc(_plain(issue.summary, 110))}</em>
        <small>{_esc(meta)}{ask}</small>
      </span>
    </a>
    """


def _column_row(card: ColumnCard) -> str:
    who = " · ".join(part for part in (card.author, card.headline, _when(card.published_at)) if part)
    cat = card.category or ""
    return f"""
    <a class="row row-text" href="{_esc(_issue_href(card.id))}/column">
      <span>
        <b>{_esc(cat) if cat else "칼럼"}</b>
        <strong>{_esc(card.title)}</strong>
        <em>{_esc(_plain(card.column_body, 140))}</em>
        <small>{_esc(who)}</small>
      </span>
    </a>
    """


def _take_row(card: TakeCard) -> str:
    who = " · ".join(part for part in (card.author, _when(card.published_at)) if part)
    return f"""
    <a class="row row-text" href="/columns/{_esc(card.id)}">
      <span>
        <b>깊이 있는 생각</b>
        <strong>{_esc(card.title)}</strong>
        <em>{_esc(_plain(card.body, 140))}</em>
        <small>{_esc(who)}</small>
      </span>
    </a>
    """


@router.get("/", response_class=HTMLResponse)
def home(db: Session = Depends(get_db)) -> HTMLResponse:
    site = SiteService(db)
    items = site.issues(limit=9, sort="trending")
    columns = site.columns(limit=4)
    takes = site.takes(limit=4)
    featured = next((item for item in items if item.image_url), items[0] if items else None)
    rest = [item for item in items if not featured or item.id != featured.id][:6]
    parts: list[str] = ['<main>']
    if featured:
        parts.append(_hero(featured))
    else:
        parts.append(
            '<section class="empty"><h1>TAKELEY</h1>'
            "<p>이슈를 읽고, 한 번 눌러 생각을 남기는 곳입니다. 아직 공개된 이슈가 없습니다.</p>"
            "</section>"
        )
    if rest:
        rows = "".join(_issue_row(item, logo_fallback=True) for item in rest)
        parts.append(
            f'<section class="block"><div class="block-head"><h2>지금 보는 이슈</h2>'
            f'<a href="/issues">더보기</a></div><div class="rows">{rows}</div></section>'
        )
    if columns:
        rows = "".join(_column_row(card) for card in columns)
        parts.append(
            f'<section class="block"><div class="block-head"><h2>칼럼</h2>'
            f'<a href="/columns">더보기</a></div><div class="rows">{rows}</div></section>'
        )
    if takes:
        rows = "".join(_take_row(card) for card in takes)
        parts.append(
            '<section class="block"><div class="block-head"><h2>깊이 있는 생각</h2>'
            f'<a href="/columns">더보기</a></div><div class="rows">{rows}</div></section>'
        )
    parts.append("</main>")
    return _page(
        title="TAKELEY — 이슈를 보고, 생각을 남기다",
        og_title="TAKELEY",
        description="테이클리 — 이슈를 짧게 읽고, 한 번 눌러 생각을 남기는 곳입니다.",
        path="/",
        body="".join(parts),
        image="/static/og-splash.png",
        image_width=1200,
        image_height=1200,
    )


@router.get("/issues", response_class=HTMLResponse)
def issues_page(
    category: str | None = Query(None, max_length=32),
    q: str | None = Query(None, max_length=40),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    site = SiteService(db)
    labels = site.categories_in_use()
    requested = (category or "").strip()
    active = requested if requested in labels else ""
    items = site.issues(limit=24, sort="new", category=requested or None, q=q)
    chips = ['<a class="chip{}" href="/issues">전체</a>'.format("" if active else " is-on")]
    for label in labels:
        on = " is-on" if label == active else ""
        chips.append(
            f'<a class="chip{on}" href="/issues?category={quote(label)}">{_esc(label)}</a>'
        )
    query = (q or "").strip()
    head = "검색 결과" if query else (active or "이슈")
    rows = "".join(_issue_row(item, logo_fallback=True) for item in items) or (
        '<p class="empty">해당하는 이슈가 없습니다.</p>'
    )
    body = f"""
    <main>
      <h1>{_esc(head)}</h1>
      <div class="chips">{''.join(chips)}</div>
      <div class="rows">{rows}</div>
    </main>
    """
    desc = "TAKELEY에서 다루는 이슈입니다. 읽고, 생각을 남겨 보세요."
    if query:
        desc = f"‘{query}’ 검색"
    return _page(title=f"{head} · TAKELEY", description=desc, path="/issues", body=body)


@router.get("/issues/{issue_id}", response_class=HTMLResponse)
def issue_page(issue_id: str, db: Session = Depends(get_db)) -> HTMLResponse:
    site = SiteService(db)
    issue = site.issue(issue_id)
    if not issue or issue.status != "published":
        raise HTTPException(status_code=404, detail="Issue not found")
    summary = (issue.summary or "").strip()
    body = f"""
    <main class="read">
      {_issue_story(issue, include_column_body=False)}
      {_vote_html(issue)}
      <p class="app-note"><a href="{_esc(_ios_store_url())}">댓글은 모바일 앱에서 남길 수 있어요.</a></p>
    </main>
    {_vote_script(issue.id)}
    """
    return _page(
        title=f"{issue.title} · TAKELEY",
        description=summary or issue.title,
        path=_issue_href(issue.id),
        body=body,
        image=_abs_media(issue.image_url) or _LOGO,
    )


@router.get("/issues/{issue_id}/column", response_class=HTMLResponse)
def column_page(issue_id: str, db: Session = Depends(get_db)) -> HTMLResponse:
    issue = SiteService(db).issue(issue_id)
    if not issue or issue.status != "published" or not (issue.column_body or "").strip():
        raise HTTPException(status_code=404, detail="Column not found")
    column = _render_column_html(issue.column_body or "", site_origin())
    body = f"""
    <main class="read">
      <p class="eyebrow">COLUMN</p>
      <h1>{_esc(issue.title)}</h1>
      {f'<p class="dek">{_esc(issue.summary.strip())}</p>' if (issue.summary or "").strip() else ''}
      {_byline(issue)}
      {_cover(issue)}
      <div class="prose">{column}</div>
      <p class="back"><a href="{_esc(_issue_href(issue.id))}">이 이슈로 돌아가기</a></p>
    </main>
    """
    return _page(
        title=f"{issue.title} · TAKELEY",
        description=_plain(issue.column_body, 160),
        path=f"{_issue_href(issue.id)}/column",
        body=body,
        image=_abs_media(issue.image_url) or _LOGO,
    )


def _issue_story(issue: IssueOut, *, include_column_body: bool) -> str:
    cat = (issue.category or "").strip()
    summary = (issue.summary or "").strip()
    why = (issue.why_it_matters or "").strip()
    why_html = (
        f'<section class="block-text"><h2>왜 중요한가</h2><p>{_esc(why)}</p></section>'
        if why
        else ""
    )
    points = [point.strip() for point in (issue.key_points or []) if point and str(point).strip()]
    points_html = ""
    if points:
        items = "".join(f"<li>{_esc(point)}</li>" for point in points[:8])
        points_html = f'<section class="block-text"><h2>핵심만 보면</h2><ul>{items}</ul></section>'
    column_link = ""
    if (issue.column_body or "").strip() and not include_column_body:
        column_link = (
            f'<p class="column-cta"><a class="pill" href="{_esc(_issue_href(issue.id))}/column">컬럼 자세히 보기</a></p>'
            '<p class="hint">이 이슈를 긴 글로 읽어 보세요</p>'
        )
    return f"""
      {f'<p class="kicker dark">{_esc(cat)}</p>' if cat else ''}
      <h1>{_esc(issue.title)}</h1>
      {f'<p class="dek">{_esc(summary)}</p>' if summary else ''}
      {_byline(issue)}
      {_cover(issue)}
      {why_html}
      {points_html}
      {column_link}
    """


def _cover(issue: IssueOut) -> str:
    photo = _photo(issue.image_url)
    if not photo:
        return ""
    return f'<div class="cover">{photo}</div>'


def _byline(issue: IssueOut) -> str:
    name = (issue.column_author_name or "").strip()
    if not name:
        return ""
    image = _abs_media(issue.column_author_image_url)
    avatar = (
        f'<img class="avatar" src="{_esc(image)}" alt="" />'
        if image
        else f'<span class="avatar">{_esc(name[:1])}</span>'
    )
    minutes = _read_minutes(issue)
    when = _when(issue.content_updated_at or issue.published_at)
    meta = " · ".join(
        part
        for part in (
            f"{when} 업데이트" if when else "",
            f"{minutes}분 읽기" if minutes else "",
        )
        if part
    )
    return f'<div class="byline-row">{avatar}<span><strong>{_esc(name)}</strong><small>{_esc(meta)}</small></span></div>'


def _read_minutes(issue: IssueOut) -> int:
    body = (issue.column_body or "").strip() or f"{issue.summary}{issue.why_it_matters}"
    chars = len(re.sub(r"\s+", "", body))
    if chars <= 0:
        return 1
    return max(1, min(999, round(chars / 500)))


def _vote_html(issue: IssueOut) -> str:
    if not issue.participation_suitable or not issue.options:
        return '<p class="dek">이 이슈는 읽어 보는 글입니다.</p>'
    question = (issue.participation_question or "").strip() or "이 이슈, 어떻게 생각해?"
    buttons = []
    for option in sorted(issue.options, key=lambda item: item.display_order):
        buttons.append(
            f'<button type="button" class="opt js-vote" data-option-id="{_esc(option.id)}">'
            f'<span class="opt-label">{_esc(option.label)}</span>'
            f'<span class="opt-pct"></span>'
            f"</button>"
        )
    return f"""
    <section class="vote" id="take">
      <p class="kicker dark">당신의 생각은?</p>
      <h2>{_esc(question)}</h2>
      {''.join(buttons)}
      <button type="button" class="pill js-confirm" hidden>결과 보기</button>
      <p class="hint js-lock">선택한 뒤에 다른 사람 생각을 볼 수 있어요.</p>
      <p class="hint js-count" hidden></p>
    </section>
    """


def _vote_script(issue_id: str) -> str:
    import json

    return """
<script>
(function () {
  var issueId = %s;
  var box = document.getElementById("take");
  if (!box) return;
  var voting = false;
  var pending = "";
  function ensureUser() {
    var deviceKey = "takeley_web_device_id";
    var userKey = "takeley_web_user_id";
    var deviceId = localStorage.getItem(deviceKey);
    var userId = localStorage.getItem(userKey);
    if (userId && deviceId && deviceId.length >= 8) return Promise.resolve(userId);
    if (!deviceId || deviceId.length < 8) {
      deviceId = "web-" + (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()));
      localStorage.setItem(deviceKey, deviceId);
    }
    return fetch("/api/v1/devices/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id: deviceId, platform: "web" })
    }).then(function (res) { return res.ok ? res.json() : null; }).then(function (data) {
      var id = data && data.user && data.user.id;
      if (!id) return "";
      localStorage.setItem(userKey, id);
      return id;
    }).catch(function () { return ""; });
  }
  function reveal(options, myId, participationCount, distributionVisible) {
    var total = Number(participationCount) || 0;
    var showDist = distributionVisible === true && total > 0;
    box.classList.add("is-voted");
    box.querySelectorAll(".js-vote").forEach(function (btn) {
      var id = btn.getAttribute("data-option-id");
      var match = null;
      options.forEach(function (o) { if (o.id === id) match = o; });
      if (!match) return;
      var pct = total > 0 ? Math.round((Number(match.count) || 0) / total * 100) : 0;
      var pctEl = btn.querySelector(".opt-pct");
      if (pctEl) {
        pctEl.textContent = showDist ? (pct + "%% · " + (Number(match.count) || 0)) : "";
      }
      btn.classList.toggle("is-mine", id === myId);
    });
    var confirm = box.querySelector(".js-confirm");
    var lock = box.querySelector(".js-lock");
    var count = box.querySelector(".js-count");
    if (confirm) confirm.hidden = true;
    if (lock) lock.hidden = true;
    if (count) {
      count.hidden = false;
      if (total > 0) {
        count.textContent = showDist
          ? (total + "명 생각 남김")
          : (total + "명 생각 남김 · 비율은 더 모이면 공개");
      } else {
        count.textContent = "아직 충분한 응답이 모이지 않았어요.";
      }
    }
  }
  function vote(optionId) {
    if (voting || !optionId || box.classList.contains("is-voted")) return;
    voting = true;
    ensureUser().then(function (userId) {
      if (!userId) { voting = false; return; }
      return fetch("/api/v1/issues/" + encodeURIComponent(issueId) + "/participate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ option_id: optionId, user_id: userId })
      }).then(function (res) { return res.ok ? res.json() : null; }).then(function (data) {
        if (data && data.options) {
          reveal(
            data.options,
            data.my_option_id || optionId,
            data.participation_count,
            data.distribution_visible
          );
        }
      }).finally(function () { voting = false; });
    });
  }
  box.querySelectorAll(".js-vote").forEach(function (btn) {
    btn.addEventListener("click", function () {
      if (box.classList.contains("is-voted") || voting) return;
      pending = btn.getAttribute("data-option-id") || "";
      box.querySelectorAll(".js-vote").forEach(function (el) {
        el.classList.toggle("is-pending", el === btn);
      });
      var confirm = box.querySelector(".js-confirm");
      var lock = box.querySelector(".js-lock");
      if (confirm) confirm.hidden = false;
      if (lock) lock.textContent = "다른 선택지를 누르면 바꿀 수 있어요.";
    });
  });
  var confirm = box.querySelector(".js-confirm");
  if (confirm) confirm.addEventListener("click", function () { if (pending) vote(pending); });
  ensureUser().then(function (userId) {
    if (!userId) return;
    return fetch("/api/v1/issues/" + encodeURIComponent(issueId) + "?user_id=" + encodeURIComponent(userId))
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) {
        if (data && data.my_option_id && data.options) {
          reveal(
            data.options,
            data.my_option_id,
            data.participation_count,
            data.distribution_visible
          );
        }
      });
  });
})();
</script>
""" % json.dumps(issue_id)


@router.get("/columns", response_class=HTMLResponse)
def columns_page(db: Session = Depends(get_db)) -> HTMLResponse:
    site = SiteService(db)
    columns = site.columns(limit=24)
    takes = site.takes(limit=12)
    parts = ["<main><h1>칼럼</h1>", "<p class=\"dek\">이슈를 한 걸음 더 읽습니다. 생각을 남기지 않아도 볼 수 있습니다.</p>"]
    if columns:
        parts.append(f'<div class="rows">{"".join(_column_row(card) for card in columns)}</div>')
    if takes:
        parts.append("<h2>깊이 있는 생각</h2>")
        parts.append(f'<div class="rows">{"".join(_take_row(card) for card in takes)}</div>')
    if not columns and not takes:
        parts.append('<p class="empty">아직 공개된 칼럼이 없습니다.</p>')
    parts.append("</main>")
    return _page(
        title="칼럼 · TAKELEY",
        description="이슈를 해설하는 칼럼과 깊이 있는 생각입니다.",
        path="/columns",
        body="".join(parts),
    )


@router.get("/columns/{take_id}", response_class=HTMLResponse)
def take_page(take_id: str, db: Session = Depends(get_db)) -> HTMLResponse:
    card = SiteService(db).take(take_id)
    if not card:
        raise HTTPException(status_code=404, detail="Column not found")
    paragraphs = "".join(
        f"<p>{_esc(part.strip())}</p>"
        for part in re.split(r"\n\s*\n", card.body)
        if part.strip()
    )
    author = card.author or ""
    body = f"""
    <main class="read">
      <p class="eyebrow">Contributor</p>
      {f'<p class="author">{_esc(author)}</p>' if author else ''}
      <h1>{_esc(card.title)}</h1>
      <div class="prose">{paragraphs}</div>
      <p class="back"><a href="{_esc(_issue_href(card.issue_id))}">이 칼럼과 관련된 이슈 · {_esc(card.issue_title)}</a></p>
    </main>
    """
    return _page(
        title=f"{card.title} · TAKELEY",
        description=_plain(card.body, 160),
        path=f"/columns/{quote(take_id, safe='')}",
        body=body,
    )


@router.get("/about", response_class=HTMLResponse)
def about() -> HTMLResponse:
    body = """
    <main class="article">
      <p class="kicker">TAKELEY</p>
      <h1>이슈를 보고, 생각을 남깁니다.</h1>
      <div class="prose">
        <p>테이클리는 오늘의 이슈를 짧은 카드로 정리하고, 한 번 눌러 생각을 남기게 합니다. 뉴스를 쌓아 두는 곳이 아닙니다.</p>
        <p>웹에서는 이슈와 칼럼을 읽고, 선택하면 결과가 이 페이지에 보입니다. 앱에서는 같은 이슈를 팔로우하고, 알림으로 다시 돌아옵니다.</p>
        <p>칼럼은 읽기 위해 선택을 요구하지 않습니다. 생각은 그 다음 행동입니다.</p>
      </div>
    </main>
    """
    return _page(
        title="테이클리 · TAKELEY",
        description="이슈를 발견하고, 이해하고, 생각을 남기는 테이클리입니다.",
        path="/about",
        body=body,
    )


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots() -> PlainTextResponse:
    origin = site_origin()
    return PlainTextResponse(f"User-agent: *\nAllow: /\nSitemap: {origin}/sitemap.xml\n")


@router.get("/sitemap.xml")
def sitemap(db: Session = Depends(get_db)) -> Response:
    origin = site_origin()
    site = SiteService(db)
    locs = ["/", "/issues", "/columns", "/about", "/privacy", "/terms", "/support"]
    for item in site.issues(limit=50, sort="new"):
        locs.append(_issue_href(item.id))
    for card in site.takes(limit=20):
        locs.append(f"/columns/{card.id}")
    body = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path in locs:
        body.append(f"<url><loc>{_esc(origin + path)}</loc></url>")
    body.append("</urlset>")
    return Response("".join(body), media_type="application/xml")


_CSS = """
:root {
  --fg: #111;
  --muted: #5c6570;
  --line: #e6e8ee;
  --bg: #fff;
  --accent: #2D5BE3;
  --ink: #10141c;
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
html, body { overflow-anchor: none; }
body {
  margin: 0;
  color: var(--fg);
  background: #f4f5f7;
  font-family: "Pretendard", "Apple SD Gothic Neo", system-ui, sans-serif;
  line-height: 1.5;
}
a { color: inherit; }
.shell { max-width: 1080px; margin: 0 auto; background: var(--bg); min-height: 100vh; }
.top, .foot {
  display: flex;
  align-items: center;
  gap: 22px;
  padding: 18px 28px;
}
.top {
  position: sticky;
  top: 0;
  z-index: 20;
  background: #fff;
  border-bottom: 1px solid var(--line);
}
.logo {
  font-weight: 800;
  letter-spacing: 0.04em;
  color: var(--accent);
  text-decoration: none;
  margin: 0;
}
.nav { display: flex; gap: 16px; }
.nav a { text-decoration: none; font-weight: 700; font-size: 15px; }
.search { margin-left: auto; }
.search input {
  width: 220px;
  border: 0;
  border-bottom: 1px solid var(--line);
  padding: 8px 0;
  font-size: 14px;
  background: transparent;
}
.search input:focus { outline: none; border-color: var(--accent); }
main { padding: 28px 28px 12px; }
h1 { margin: 0 0 12px; font-size: 32px; letter-spacing: -0.03em; line-height: 1.25; }
h2 { margin: 0; font-size: 22px; letter-spacing: -0.03em; }
.dek, .empty { color: var(--muted); }
.hero {
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  align-items: center;
  text-decoration: none;
  margin-bottom: 36px;
}
.hero-media { overflow: hidden; border-radius: 16px; }
.hero-media img, .hero-fallback {
  width: 100%;
  height: 360px;
  object-fit: cover;
  border-radius: 16px;
  display: block;
  background: #d9dee8;
}
.hero-plain .hero-copy { margin-left: 0; }
.hero-copy {
  margin-left: -48px;
  padding: 32px 28px;
  border-radius: 16px;
  background: var(--ink);
  color: #fff;
}
.hero-copy h1 { font-size: 30px; }
.hero-copy p { margin: 12px 0 0; color: #d5dbe6; }
.kicker, .hero-copy .kicker {
  margin: 0 0 8px;
  color: #9eb6ff;
  font-size: 13px;
  font-weight: 700;
}
.badge {
  display: inline-block;
  margin-bottom: 8px;
  color: #9eb6ff;
  font-size: 12px;
  font-weight: 700;
}
.hero-ask { display: inline-block; margin-top: 18px; color: #fff; font-weight: 700; }
.block { margin: 12px 0 36px; }
.block-head, .chips {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.block-head a, .foot a { color: var(--accent); text-decoration: none; font-weight: 700; font-size: 14px; }
.rows { display: grid; grid-template-columns: 1fr 1fr; column-gap: 24px; }
.row {
  display: grid;
  grid-template-columns: 112px 1fr;
  gap: 14px;
  padding: 16px;
  border-top: 1px solid var(--line);
  text-decoration: none;
}
.row img, .thumb {
  width: 112px;
  height: 76px;
  object-fit: cover;
  border-radius: 8px;
  background: #e8ebf2;
}
.hero-media img.is-logo {
  object-fit: contain;
  background: #2D5BE3;
  padding: 18%;
}
.row img.is-logo {
  object-fit: cover;
  object-position: center;
  background: #000;
  padding: 0;
}
.row strong { display: block; font-size: 16px; letter-spacing: -0.02em; }
.row em, .row small { display: block; font-style: normal; color: var(--muted); }
.row em { margin-top: 4px; font-size: 14px; }
.row small { margin-top: 6px; font-size: 12px; }
.row-text { grid-template-columns: 1fr; }
.row b { color: var(--accent); font-size: 12px; }
.ask { margin-left: 8px; color: var(--accent); font-weight: 700; }
.chips { justify-content: flex-start; flex-wrap: wrap; margin: 8px 0 18px; }
.chip {
  text-decoration: none;
  color: var(--muted);
  font-weight: 700;
  margin-right: 14px;
}
.chip.is-on { color: var(--fg); }
.btn, .pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 52px;
  padding: 12px 22px;
  border: 0;
  border-radius: 999px;
  background: var(--accent);
  color: #fff;
  font-weight: 700;
  font-size: 16px;
  letter-spacing: -0.02em;
  text-decoration: none;
  cursor: pointer;
  box-shadow: 4px 4px 0 #0A0A0A;
  transition: transform 80ms ease, box-shadow 80ms ease;
}
.btn:active, .pill:active {
  transform: translate(2px, 2px);
  box-shadow: 2px 2px 0 #0A0A0A;
}
.btn.ghost {
  min-height: 44px;
  padding: 10px 18px;
  background: #fff;
  color: #111;
  font-size: 15px;
  box-shadow: none;
  border: 1px solid rgba(0, 0, 0, 0.12);
}
.btn.ghost:active { transform: none; box-shadow: none; }
.read { max-width: 40rem; margin: 0 auto; }
.read h1 { font-size: 26px; font-weight: 800; letter-spacing: -0.03em; }
.eyebrow { margin: 0 0 12px; color: var(--accent); font-size: 11px; font-weight: 700; letter-spacing: 0.08em; }
.author { margin: 0 0 8px; color: #444; font-weight: 600; }
.cover { margin: 8px 0 20px; }
.cover img { width: 100%; height: auto; max-height: none; border-radius: 12px; object-fit: cover; }
.cover img.is-logo {
  height: 220px;
  object-fit: cover;
  object-position: center;
  background: #000;
}
.byline-row { display: flex; align-items: center; gap: 10px; margin: 16px 0; }
.avatar {
  width: 40px; height: 40px; border-radius: 50%;
  object-fit: cover; background: #e8ebf2;
  display: inline-grid; place-items: center; font-weight: 700;
}
.byline-row small { display: block; color: #444; font-size: 12px; font-weight: 400; }
.block-text { margin-top: 28px; }
.block-text h2 { font-size: 18px; margin-bottom: 8px; }
.block-text p, .block-text li { font-size: 16px; line-height: 1.55; }
.column-cta { margin: 20px 0 0; }
.hint { margin: 8px 0 0; color: var(--muted); font-size: 13px; text-align: center; }
.app-note { margin: 28px 0 8px; color: var(--muted); font-size: 13px; text-align: center; }
.app-note a { color: var(--accent); font-weight: 700; text-decoration: none; }
.column-cta .pill, .vote .pill {
  display: flex;
  width: 100%;
}
.back { margin-top: 28px; }
.back a { color: var(--accent); font-weight: 700; }
.article { max-width: 42rem; }
.byline { color: var(--muted); }
.prose p { font-size: 17px; }
.prose, .column { max-width: 100%; }
.column img, .prose img {
  max-width: 100%;
  height: auto;
}
.column .body-img, .prose .body-img {
  display: block;
  width: 100%;
  border-radius: 12px;
  margin: 0 0 1.1rem;
}
.column .inline-img, .prose .inline-img {
  display: inline-block;
  width: auto;
  max-width: 100%;
  height: auto;
  vertical-align: middle;
}
.related-issue { margin-top: 28px; }
.related-issue a { color: var(--accent); font-weight: 700; }
.foot {
  border-top: 1px solid var(--line);
  align-items: flex-start;
  padding-bottom: 40px;
}
.foot nav { display: flex; flex-wrap: wrap; gap: 12px 16px; margin-left: auto; }
.foot p { margin: 4px 0 0; color: var(--muted); font-size: 14px; }
.kicker.dark { color: var(--accent); }
.issue-hero {
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  gap: 28px;
  align-items: end;
  margin-bottom: 32px;
}
.issue-hero .hero-fallback, .issue-hero img { height: 380px; }
.lead { font-size: 18px; color: #243041; }
.issue-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 36px;
  align-items: start;
}
.vote, .side-links {
  padding: 18px 16px 16px;
  border-radius: 16px;
  background: #F7F8FA;
}
.vote { position: sticky; top: 16px; }
.vote h2, .side-links h2 { font-size: 18px; margin-bottom: 8px; }
.opt {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 52px;
  margin-top: 8px;
  padding: 12px 16px;
  border: 1.5px solid rgba(45, 91, 227, 0.35);
  border-radius: 12px;
  background: #fff;
  color: #111;
  text-align: left;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
}
.opt.is-pending, .opt.is-mine {
  background: #E8EEFC;
  border-color: var(--accent);
}
.opt-pct { color: var(--muted); font-size: 13px; font-weight: 500; }
.vote-fill {
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 0;
  background: rgba(45, 91, 227, 0.14);
  transition: width 0.55s ease;
}
.opt-label, .opt-pct { position: relative; }
.js-confirm { margin-top: 12px; }
.voted-note { color: var(--accent); font-weight: 700; }
.side-links a {
  display: block;
  padding: 10px 0;
  border-top: 1px solid var(--line);
  text-decoration: none;
  font-weight: 700;
}
.hero, .issue-hero, .block { animation: rise 0.6s ease both; }
.row { animation: rise 0.55s ease both; }
.row:nth-child(2) { animation-delay: 0.05s; }
.row:nth-child(3) { animation-delay: 0.1s; }
.row:nth-child(4) { animation-delay: 0.15s; }
@media (hover: hover) {
  .hero-media img { transition: transform 0.7s ease; }
  .hero:hover .hero-media img, .issue-hero:hover .hero-media img { transform: scale(1.04); }
  .hero-copy { transition: transform 0.45s ease; }
  .hero:hover .hero-copy { transform: translate(-6px, -6px); }
}
.row:hover { background: #f7f8fb; }
@keyframes rise {
  from { opacity: 0; }
  to { opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation: none !important;
    transition: none !important;
  }
}
@media (max-width: 800px) {
  .top, .foot, main { padding-left: 16px; padding-right: 16px; }
  .top { flex-wrap: wrap; }
  .search { margin-left: 0; width: 100%; }
  .search input { width: 100%; font-size: 16px; }
  .hero, .rows, .foot, .issue-hero, .issue-layout { grid-template-columns: 1fr; display: block; }
  .hero-copy { margin: -36px 12px 0; }
  .hero-plain .hero-copy { margin: 0; }
  .issue-hero .hero-fallback, .issue-hero img { height: 220px; }
  .vote { position: static; margin-top: 20px; }
  .row { grid-template-columns: 84px 1fr; }
  .row-text { grid-template-columns: 1fr; }
  .row img, .thumb { width: 84px; height: 64px; }
  .foot nav { margin: 14px 0 0; }
}
.app-qr { display: none; }
@media (min-width: 1320px) {
  .app-qr {
    display: block;
    position: fixed;
    z-index: 15;
    top: 88px;
    left: calc(50% + 540px + 12px);
    width: max-content;
    padding: 8px 10px 7px;
    background: #fff;
    border: 1px solid var(--line);
    border-radius: 12px;
    text-align: center;
    color: inherit;
    text-decoration: none;
  }
  .app-qr img { width: 68px; height: 68px; display: block; margin: 0 auto; }
  .app-qr span {
    display: block;
    margin-top: 4px;
    font-size: 11px;
    line-height: 1.3;
    white-space: nowrap;
    font-weight: 700;
    color: var(--muted);
  }
}
"""
