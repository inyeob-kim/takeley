"""NEWS card generation — short feed summary + longer detail body."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.pipeline.prompts import NEWS_CARD_PROMPT, NEWS_CARD_PROMPT_VERSION

logger = logging.getLogger(__name__)

_ALLOWED_CATEGORIES = frozenset(
    {"정치", "경제", "금융", "기술", "AI", "사회", "국제", "문화", "스포츠", "엔터"}
)

# Audit of prod v3 cards: title-token coverage in summary for title≈summary
# failures clustered around ≥0.55; clearer cards were typically ≤0.40.
_TITLE_SUMMARY_COVERAGE_REJECT = 0.55

_FORBIDDEN_EXTRA_KEYS = frozenset(
    {"takeley_line", "angle", "opinion", "question", "cta"}
)

_CTA_RE = re.compile(
    r"(여러분의\s*생각은|당신이라면|찬성하시나요|반대하시나요|어떻게\s*생각하시나요)",
    re.I,
)

_TOKEN_RE = re.compile(r"[가-힣]{2,}|[A-Za-z0-9]+")

_BODY_MIN_CHARS = 350
_BODY_MAX_CHARS = 900


@dataclass
class NewsCard:
    title: str
    summary: str
    body: str = ""
    key_points: list[str] = field(default_factory=list)
    category: str | None = None
    source: str = "heuristic"  # heuristic | llm
    ok: bool = True
    reason: str = ""


def _clip(text: str, n: int) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    if len(t) <= n:
        return t
    return t[: n - 1].rstrip() + "…"


def _normalize_body(text: str, *, max_chars: int = 4500) -> str:
    """Keep markdown headings/bold and paragraph breaks; tidy whitespace."""
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not raw:
        return ""
    lines = [re.sub(r"[ \t]+", " ", ln).rstrip() for ln in raw.split("\n")]
    out: list[str] = []
    blank = False
    for ln in lines:
        if not ln.strip():
            if out and not blank:
                out.append("")
                blank = True
            continue
        blank = False
        out.append(ln.strip())
    body = "\n".join(out).strip()
    if len(body) <= max_chars:
        return body
    cut = body[: max_chars - 1]
    # Prefer cutting at paragraph boundary
    if "\n\n" in cut:
        cut = cut.rsplit("\n\n", 1)[0]
    else:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip() + "…"


def _significant_tokens(text: str) -> set[str]:
    return {m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")}


def _compact_for_overlap(text: str) -> str:
    """Lowercase + strip spaces/punct so josa-attached forms still match stems."""
    t = (text or "").lower()
    return re.sub(r"[\s,./·…\-_|:;'\"“”‘’]+", "", t)


def title_summary_token_coverage(title: str, summary: str) -> float:
    """Fraction of title tokens that appear as substrings in the summary.

    Uses substring match (not exact tokens) so Korean josa variants still count —
    e.g. title 「생산」 vs summary 「생산을」. Threshold 0.55 was chosen from prod
    audit: title≈summary failures had high stem coverage; distinct summaries were lower.
    """
    title_toks = _significant_tokens(title)
    if not title_toks:
        return 0.0
    hay = _compact_for_overlap(summary)
    hits = 0
    for tok in title_toks:
        stem = _compact_for_overlap(tok)
        if stem and stem in hay:
            hits += 1
    return hits / len(title_toks)


def count_markdown_headings(body: str) -> int:
    return sum(
        1
        for ln in (body or "").splitlines()
        if ln.lstrip().startswith("## ")
    )


def count_bold_phrases(body: str) -> int:
    return len(re.findall(r"\*\*[^*]+\*\*", body or ""))


def has_issue_style_cta(*parts: str) -> bool:
    blob = "\n".join(p or "" for p in parts)
    return bool(_CTA_RE.search(blob))


def llm_payload_has_forbidden_keys(data: dict) -> str | None:
    for key in _FORBIDDEN_EXTRA_KEYS:
        if key not in data:
            continue
        val = data.get(key)
        if val is None or val is False:
            continue
        if isinstance(val, str) and not val.strip():
            continue
        if isinstance(val, (list, dict)) and not val:
            continue
        return key
    return None


def apply_news_card_post_check(card: NewsCard) -> NewsCard:
    """Cheap deterministic validation after LLM/heuristic structuring.

    LLM cards: full v5 checks (length, title≈summary, ##, CTA).
    Heuristic fallback: only structural CTA / heading guards — source paste
    often mirrors the title and can be shorter than the briefing target.
    """
    if not card.ok:
        return card

    title = (card.title or "").strip()
    summary = (card.summary or "").strip()
    body = card.body or ""

    if len(title) < 4 or len(summary) < 8:
        card.ok = False
        card.reason = "too_short"
        return card

    if has_issue_style_cta(title, summary, body):
        card.ok = False
        card.reason = "issue_style_cta"
        return card

    headings = count_markdown_headings(body)
    if headings >= 2:
        card.ok = False
        card.reason = "too_many_headings"
        return card

    if card.source != "llm":
        return card

    # Soft clip overlong bodies to the v5 briefing band.
    if len(body) > _BODY_MAX_CHARS:
        body = _normalize_body(body, max_chars=_BODY_MAX_CHARS)
        card.body = body

    if len(body) < _BODY_MIN_CHARS:
        card.ok = False
        card.reason = "body_too_short"
        return card

    coverage = title_summary_token_coverage(title, summary)
    if coverage >= _TITLE_SUMMARY_COVERAGE_REJECT:
        card.ok = False
        card.reason = "title_summary_overlap"
        return card

    if count_bold_phrases(body) > 2:
        card.ok = False
        card.reason = "too_many_bold"
        return card

    return card


def _heuristic_news(
    *,
    text: str,
    source_title: str | None,
    provider: str,
) -> NewsCard:
    title = (source_title or "").strip()
    body_src = (text or "").strip()
    if not title:
        title = re.split(r"[.!?\n]", body_src)[0].strip() or body_src[:80]
    title = _clip(title, 120)
    summary_src = body_src
    if source_title and body_src.lower().startswith(source_title.lower()):
        summary_src = body_src[len(source_title) :].lstrip(" .-:")
    summary = _clip(summary_src or title, 400)
    body = _normalize_body(summary_src or body_src, max_chars=2500)
    if len(title) < 4 or len(summary) < 8:
        return NewsCard(
            title=title or "",
            summary=summary or "",
            body=body,
            ok=False,
            reason="too_short",
            source="heuristic",
        )
    return apply_news_card_post_check(
        NewsCard(
            title=title,
            summary=summary,
            body=body,
            key_points=[],
            category=None,
            source="heuristic",
            ok=True,
        )
    )


def generate_news_card(
    *,
    text: str,
    provider: str,
    source_title: str | None = None,
    source_url: str | None = None,
) -> NewsCard:
    settings = get_settings()
    if not settings.openai_api_key:
        return _heuristic_news(
            text=text, source_title=source_title, provider=provider
        )
    try:
        from openai import OpenAI

        from app.core.usage import record_llm_usage

        client = OpenAI(api_key=settings.openai_api_key)
        # Full article body when available (RSS enrich); keep prompt bounded.
        prompt = NEWS_CARD_PROMPT.format(
            provider=provider or "unknown",
            source_title=(source_title or "")[:200] or "(none)",
            source_url=(source_url or "")[:500] or "(none)",
            text=(text or "")[:6000],
        )
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        record_llm_usage(resp, stage="news_generate", model=settings.openai_model)
        data = json.loads(resp.choices[0].message.content or "{}")
        if not isinstance(data, dict):
            return NewsCard(
                title="",
                summary="",
                ok=False,
                reason="invalid_json_object",
                source="llm",
            )
        forbidden = llm_payload_has_forbidden_keys(data)
        if forbidden:
            return NewsCard(
                title=str(data.get("title") or "").strip(),
                summary=str(data.get("summary") or "").strip(),
                body=_normalize_body(str(data.get("body") or "")),
                ok=False,
                reason=f"forbidden_field:{forbidden}",
                source="llm",
            )
        title = str(data.get("title") or "").strip()
        summary = str(data.get("summary") or "").strip()
        body = _normalize_body(
            str(data.get("body") or ""), max_chars=_BODY_MAX_CHARS
        )
        points_raw = data.get("key_points") or []
        if not isinstance(points_raw, list):
            points_raw = []
        key_points = [str(p).strip() for p in points_raw if str(p).strip()][:3]
        cat = data.get("category")
        category = None
        if cat is not None and str(cat).strip() in _ALLOWED_CATEGORIES:
            category = str(cat).strip()
        if len(title) < 4 or len(summary) < 8:
            fallback = _heuristic_news(
                text=text, source_title=source_title, provider=provider
            )
            if not fallback.ok:
                return NewsCard(
                    title=title,
                    summary=summary,
                    body=body,
                    ok=False,
                    reason="llm_too_short",
                    source="llm",
                )
            return fallback
        if len(body) < 80:
            # Prefer a readable detail body from source over a near-empty LLM body.
            heur = _heuristic_news(
                text=text, source_title=source_title, provider=provider
            )
            if len(heur.body) > len(body):
                body = _normalize_body(heur.body, max_chars=_BODY_MAX_CHARS)
        card = NewsCard(
            title=_clip(title, 200),
            summary=_clip(summary, 800),
            body=body,
            key_points=key_points,
            category=category,
            source="llm",
            ok=True,
        )
        return apply_news_card_post_check(card)
    except Exception:
        logger.exception(
            "news_generate llm failed version=%s; heuristic fallback",
            NEWS_CARD_PROMPT_VERSION,
        )
        return _heuristic_news(
            text=text, source_title=source_title, provider=provider
        )
