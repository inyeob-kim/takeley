"""LLM Understanding — semantic read + NEWS|ISSUE|REJECT classification."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.pipeline.prompts import (
    ISSUE_UNDERSTANDING_PROMPT,
    ISSUE_UNDERSTANDING_PROMPT_VERSION,
)

logger = logging.getLogger(__name__)

CONTENT_KIND_NEWS = "NEWS"
CONTENT_KIND_ISSUE = "ISSUE"
CONTENT_KIND_REJECT = "REJECT"
_VALID_KINDS = frozenset(
    {CONTENT_KIND_NEWS, CONTENT_KIND_ISSUE, CONTENT_KIND_REJECT}
)

_OPINION_RE = re.compile(
    r"\b(i think|i believe|imo|in my opinion|내가 보기에|개인적으로)\b",
    re.I,
)
_EVENT_RE = re.compile(
    r"\b(announce|announced|reports?|delay|launch|filed|ruling|unveils?|"
    r"발표|출시|판결|지연)\b",
    re.I,
)
_DEBATE_RE = re.compile(
    r"\b(will|should|demand|debate|vs|controversy|backlash|"
    r"논란|찬반|반대|쟁점)\b",
    re.I,
)
_SENSITIVE_RE = re.compile(
    r"\b(election|president|congress|parliament|impeach|protest|"
    r"대통령|국회|선거|탄핵|시위|정당)\b",
    re.I,
)
_PROMO_RE = re.compile(
    r"\b(buy now|guaranteed profit|tipster|promo|giveaway|"
    r"무조건 수익|매수 추천)\b",
    re.I,
)
# Dull wire / PR that is "an event" but not TAKELEY-worthy.
_LOW_SURFACE_RE = re.compile(
    r"("
    r"기온|한파|폭염|강풍|바람\s*주의|날씨\s*주의|기상\s*특보|"
    r"temperature\s+drop|cold\s+snap|heat\s+wave|wind\s+advisory|weather\s+alert|"
    r"초대장\s*앱|앱\s*업데이트|앱스토어\s*업데이트|invite\s+app|"
    r"app\s+store\s+update|minor\s+update|"
    r"고객만족도|고객\s*만족도|연속\s*\d+\s*년|\d+\s*년\s*연속|"
    r"customer\s+satisfaction|consecutiv\w+\s+years?\s+(as\s+)?#?\s*1|"
    r"만족도\s*1위|서비스\s*품질\s*대상"
    r")",
    re.I,
)
_NEWS_PROVIDERS = frozenset({"news", "official", "hacker_news", "sec", "ir"})


@dataclass
class UnderstandingResult:
    is_issue_candidate: bool
    relevance: float = 0.0
    hook: float = 0.0
    useful: float = 0.0
    takeley_fit: float = 0.0
    topic: str = ""
    event: str = ""
    claim: str = ""
    entities: list[str] = field(default_factory=list)
    novelty: str = "new_development"
    participation_suitable_hint: bool = False
    content_kind: str = CONTENT_KIND_REJECT
    sensitive_review: bool = False
    reject_reason: str = ""
    raw_id: str = ""
    text: str = ""
    provider: str = ""
    source: str = "heuristic"  # heuristic | llm

    @property
    def surface_min(self) -> float:
        return min(self.hook, self.useful, self.takeley_fit)


def normalize_content_kind(raw: str | None) -> str:
    key = (raw or "").strip().upper()
    if key in _VALID_KINDS:
        return key
    return CONTENT_KIND_REJECT


def derive_is_issue_candidate(content_kind: str) -> bool:
    return content_kind == CONTENT_KIND_ISSUE


def _clamp01(value: object, default: float = 0.0) -> float:
    try:
        n = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if n < 0.0:
        return 0.0
    if n > 1.0:
        return 1.0
    return n


def _surface_head(text: str, *, max_chars: int = 280) -> str:
    """Title/lede only — body context (e.g. 기온 in climate science) must not trip rules."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    first = cleaned.split("\n", 1)[0].strip()
    return first[:max_chars]


def _apply_kind(
    kind: str,
    *,
    sensitive: bool = False,
) -> tuple[str, bool, bool]:
    """Return (content_kind, is_issue_candidate, sensitive_review).

    Sensitive NEWS is upgraded to ISSUE so auto-publish cannot fire.
    """
    kind = normalize_content_kind(kind)
    if sensitive and kind == CONTENT_KIND_NEWS:
        kind = CONTENT_KIND_ISSUE
    return kind, derive_is_issue_candidate(kind), bool(sensitive)


def apply_surface_gate(result: UnderstandingResult) -> UnderstandingResult:
    """Hard-reject NEWS/ISSUE when surface scores are too weak.

    LLM is asked to score hook / useful / takeley_fit; we enforce
    min(score) >= surface_min_score so dull wire filler cannot publish.
    """
    settings = get_settings()
    if not settings.surface_gate_enabled:
        return result
    if result.content_kind == CONTENT_KIND_REJECT:
        return result

    threshold = float(settings.surface_min_score)
    weakest = result.surface_min
    if weakest >= threshold:
        return result

    logger.info(
        "surface_gate reject kind=%s min=%.2f threshold=%.2f "
        "hook=%.2f useful=%.2f fit=%.2f topic=%s",
        result.content_kind,
        weakest,
        threshold,
        result.hook,
        result.useful,
        result.takeley_fit,
        (result.topic or "")[:40],
    )
    result.content_kind = CONTENT_KIND_REJECT
    result.is_issue_candidate = False
    result.reject_reason = "low_surface_value"
    if result.novelty in ("", "new_development"):
        result.novelty = "low_surface_value"
    return result


def _heuristic_scores_for_kind(kind: str, *, low_surface: bool) -> tuple[float, float, float, float]:
    """Return hook, useful, takeley_fit, relevance."""
    if kind == CONTENT_KIND_REJECT or low_surface:
        return 0.15, 0.15, 0.1, 0.15
    if kind == CONTENT_KIND_ISSUE:
        return 0.7, 0.65, 0.7, 0.7
    # NEWS default — clears 0.55 gate for real announcements
    return 0.65, 0.65, 0.6, 0.65


def _heuristic_understand(
    *,
    text: str,
    provider: str,
    raw_id: str = "",
) -> UnderstandingResult:
    cleaned = (text or "").strip()
    if len(cleaned) < 12:
        kind, is_issue, sens = _apply_kind(CONTENT_KIND_REJECT)
        hook, useful, fit, rel = _heuristic_scores_for_kind(kind, low_surface=True)
        return UnderstandingResult(
            is_issue,
            rel,
            hook,
            useful,
            fit,
            novelty="opinion_only",
            content_kind=kind,
            sensitive_review=sens,
            reject_reason="too_short",
            raw_id=raw_id,
            text=cleaned,
            provider=provider,
        )
    if _PROMO_RE.search(cleaned):
        kind, is_issue, sens = _apply_kind(CONTENT_KIND_REJECT)
        hook, useful, fit, rel = _heuristic_scores_for_kind(kind, low_surface=True)
        return UnderstandingResult(
            is_issue,
            rel,
            hook,
            useful,
            fit,
            novelty="opinion_only",
            content_kind=kind,
            sensitive_review=sens,
            reject_reason="promo",
            raw_id=raw_id,
            text=cleaned,
            provider=provider,
        )
    # Dull-wire patterns on title/lede only (avoid body false positives).
    if _LOW_SURFACE_RE.search(_surface_head(cleaned)):
        kind, is_issue, sens = _apply_kind(CONTENT_KIND_REJECT)
        hook, useful, fit, rel = _heuristic_scores_for_kind(kind, low_surface=True)
        return UnderstandingResult(
            is_issue,
            rel,
            hook,
            useful,
            fit,
            novelty="low_surface_value",
            content_kind=kind,
            sensitive_review=sens,
            reject_reason="low_surface_heuristic",
            raw_id=raw_id,
            text=cleaned,
            provider=provider,
        )
    if _OPINION_RE.search(cleaned) and not _EVENT_RE.search(cleaned):
        kind, is_issue, sens = _apply_kind(CONTENT_KIND_REJECT)
        hook, useful, fit, rel = _heuristic_scores_for_kind(kind, low_surface=True)
        return UnderstandingResult(
            is_issue,
            rel,
            hook,
            useful,
            fit,
            topic="opinion",
            event="",
            novelty="opinion_only",
            content_kind=kind,
            sensitive_review=sens,
            reject_reason="opinion_only",
            raw_id=raw_id,
            text=cleaned,
            provider=provider,
        )

    words = re.findall(r"[A-Za-z0-9\-\.]+", cleaned)
    topic = " ".join(words[:8]) if words else cleaned[:40]
    sensitive = bool(_SENSITIVE_RE.search(cleaned))
    debate = bool(_DEBATE_RE.search(cleaned))
    eventish = bool(_EVENT_RE.search(cleaned))
    prov = (provider or "").lower()

    if debate or sensitive:
        raw_kind = CONTENT_KIND_ISSUE
    elif eventish or prov in _NEWS_PROVIDERS:
        raw_kind = CONTENT_KIND_NEWS
    else:
        # Legacy-compatible: substance without clear NEWS markers → ISSUE path
        raw_kind = CONTENT_KIND_ISSUE

    kind, is_issue, sens = _apply_kind(raw_kind, sensitive=sensitive)
    hook, useful, fit, rel = _heuristic_scores_for_kind(kind, low_surface=False)
    result = UnderstandingResult(
        is_issue,
        rel,
        hook,
        useful,
        fit,
        topic=topic,
        event=cleaned[:160],
        claim=cleaned[:160],
        entities=words[:5],
        novelty="new_development",
        participation_suitable_hint=debate,
        content_kind=kind,
        sensitive_review=sens,
        raw_id=raw_id,
        text=cleaned,
        provider=provider,
        source="heuristic",
    )
    return apply_surface_gate(result)


def _resolve_kind_from_llm(data: dict) -> tuple[str, bool, bool]:
    """Prefer content_kind; fall back to legacy is_issue_candidate only."""
    raw_kind = data.get("content_kind")
    sensitive = bool(data.get("sensitive_review", False))
    if raw_kind is not None and str(raw_kind).strip():
        return _apply_kind(str(raw_kind), sensitive=sensitive)
    # Legacy JSON without content_kind: true→ISSUE, false→REJECT (never NEWS).
    if bool(data.get("is_issue_candidate", False)):
        return _apply_kind(CONTENT_KIND_ISSUE, sensitive=sensitive)
    return _apply_kind(CONTENT_KIND_REJECT, sensitive=sensitive)


def understand_candidate(
    *,
    text: str,
    provider: str,
    raw_id: str = "",
) -> UnderstandingResult:
    settings = get_settings()
    if not settings.openai_api_key:
        return _heuristic_understand(text=text, provider=provider, raw_id=raw_id)
    try:
        from openai import OpenAI

        from app.core.usage import record_llm_usage

        client = OpenAI(api_key=settings.openai_api_key)
        prompt = ISSUE_UNDERSTANDING_PROMPT.format(
            provider=provider or "unknown",
            text=(text or "")[:4000],
        )
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        record_llm_usage(resp, stage="understanding", model=settings.openai_model)
        data = json.loads(resp.choices[0].message.content or "{}")
        entities = data.get("entities") or []
        if not isinstance(entities, list):
            entities = []
        kind, is_issue, sensitive = _resolve_kind_from_llm(data)
        hook = _clamp01(data.get("hook"), 0.0)
        useful = _clamp01(data.get("useful"), 0.0)
        fit = _clamp01(data.get("takeley_fit"), 0.0)
        # Legacy models may omit the trio — fall back to relevance once.
        if hook == 0.0 and useful == 0.0 and fit == 0.0 and "relevance" in data:
            rel_only = _clamp01(data.get("relevance"), 0.0)
            hook = useful = fit = rel_only
        relevance = _clamp01(data.get("relevance"), (hook + useful + fit) / 3.0)
        result = UnderstandingResult(
            is_issue_candidate=is_issue,
            relevance=relevance,
            hook=hook,
            useful=useful,
            takeley_fit=fit,
            topic=str(data.get("topic") or "")[:120],
            event=str(data.get("event") or "")[:280],
            claim=str(data.get("claim") or "")[:280],
            entities=[str(e)[:64] for e in entities[:12]],
            novelty=str(data.get("novelty") or "new_development")[:64],
            participation_suitable_hint=bool(
                data.get("participation_suitable_hint", False)
            ),
            content_kind=kind,
            sensitive_review=sensitive,
            raw_id=raw_id,
            text=text,
            provider=provider,
            source="llm",
        )
        # Pattern catch on headline/lede only — body often mentions 기온 etc. in context.
        head = _surface_head(text)
        if kind != CONTENT_KIND_REJECT and _LOW_SURFACE_RE.search(head):
            result.hook = min(result.hook, 0.35)
            result.useful = min(result.useful, 0.35)
            result.takeley_fit = min(result.takeley_fit, 0.3)
            result.reject_reason = "low_surface_heuristic"
        return apply_surface_gate(result)
    except Exception:
        logger.exception(
            "understanding llm failed version=%s; heuristic fallback",
            ISSUE_UNDERSTANDING_PROMPT_VERSION,
        )
        return _heuristic_understand(text=text, provider=provider, raw_id=raw_id)


# Expose for tests
heuristic_understand = _heuristic_understand
