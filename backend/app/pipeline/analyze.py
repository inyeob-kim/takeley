"""LLM / heuristic analysis of clustered raw items into Market Signals."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from app.core.config import get_settings
from app.domain.models import EvidenceType, MarketSignal, SignalStatus
from app.pipeline.classify import classify_topic
from app.pipeline.classification import (
    heuristic_content_and_level,
    normalize_content_type,
    normalize_evidence_level,
)
from app.pipeline.cluster import Cluster
from app.pipeline.entities import default_universe_symbols, extract_sectors, extract_symbols
from app.pipeline.normalize import is_macro_theme
from app.pipeline.prompts import SIGNAL_ANALYSIS_PROMPT, SIGNAL_ANALYSIS_PROMPT_VERSION
from app.pipeline.quality import has_trusted_source, looks_like_rumor, sanitize_evidence

logger = logging.getLogger(__name__)


def _resolve_symbols(text: str, universe_symbols: list[str] | None) -> list[str]:
    extras = universe_symbols if universe_symbols is not None else default_universe_symbols()
    found = extract_symbols(text, extra_symbols=extras)
    if found:
        return found
    if is_macro_theme(text, get_settings().macro_keywords()):
        return list(get_settings().macro_index_symbol_list())
    return []


def _resolve_sectors(text: str, symbols: list[str]) -> list[str]:
    sectors = extract_sectors(text)
    if sectors:
        return sectors
    if "TSLA" in symbols:
        return ["EV"]
    if any(s in symbols for s in ("MU", "NVDA", "AVGO", "AMD")):
        return ["Semiconductor"]
    if any(s in symbols for s in ("SPY", "QQQ", "DIA")) and is_macro_theme(text):
        return ["Macro"]
    return sectors


def _source_time(cluster: Cluster) -> datetime:
    return cluster.earliest_published_at or datetime.utcnow()


def _heuristic_column_body(
    summary: str,
    why: str,
    key_points: list[str],
    texts: list[str],
) -> str:
    """Deterministic long-form when LLM is off — still readable as a column.

    Do not prepend summary — clients already show summary above the body.
    """
    parts: list[str] = []
    summary_text = summary.strip()
    why_text = why.strip()
    if why_text and why_text != summary_text:
        parts.append(why_text)
    points = [p.strip() for p in key_points if p and str(p).strip()]
    if points:
        parts.append("핵심만 정리하면 이래요.\n" + "\n".join(f"· {p}" for p in points[:5]))
    extras = [t.strip() for t in texts[:2] if t and t.strip()]
    for raw in extras:
        if raw and raw not in summary_text and raw != why_text:
            clip = raw if len(raw) <= 500 else raw[:498].rstrip() + "…"
            parts.append(clip)
    return "\n\n".join(parts)


def _clean_points(values) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if text and text not in out:
            out.append(text)
    return out[:8]


def _normalize_space(text: str) -> str:
    return " ".join((text or "").split())


def _parse_emphasis(raw, *, summary: str, why: str) -> dict:
    """Keep only emphasis tokens that actually appear in the written body."""
    body = f"{summary}\n{why}"
    body_norm = _normalize_space(body)
    data = raw if isinstance(raw, dict) else {}

    key_sentences: list[str] = []
    for item in data.get("key_sentences") or []:
        sentence = str(item or "").strip()
        if not sentence:
            continue
        if sentence in body or _normalize_space(sentence) in body_norm:
            if sentence not in key_sentences:
                key_sentences.append(sentence)
        if len(key_sentences) >= 3:
            break

    def _filter_numbers(values) -> list[str]:
        out: list[str] = []
        for item in values or []:
            token = str(item or "").strip()
            if token and token in body and token not in out:
                out.append(token)
        return out[:12]

    rise = _filter_numbers(data.get("rise_numbers"))
    fall = _filter_numbers(data.get("fall_numbers"))
    # Prefer rise if duplicated.
    fall = [t for t in fall if t not in rise]
    return {
        "key_sentences": key_sentences,
        "rise_numbers": rise,
        "fall_numbers": fall,
    }


def _heuristic_analyze(
    cluster: Cluster, *, universe_symbols: list[str] | None = None
) -> MarketSignal:
    """Fallback when LLM is unavailable. Keeps source text; labels in Korean."""
    primary = cluster.texts[0] if cluster.texts else "시장 업데이트"
    topic = classify_topic(primary)
    symbols = _resolve_symbols(primary, universe_symbols)
    sectors = _resolve_sectors(primary, symbols)

    providers = cluster.unique_providers
    rumorish = looks_like_rumor(primary)
    trusted = has_trusted_source(providers)
    content_type, evidence_level = heuristic_content_and_level(
        providers, rumorish=rumorish
    )
    key_points = [t[:280] for t in cluster.texts[:5] if t and t.strip()]

    if rumorish:
        evidence = [EvidenceType.RUMOR]
        confirmed: list[str] = []
        confidence = 0.3
        importance = 0.4
        why = (
            "아직 확인되지 않은 내용일 수 있어요. "
            "공식 발표나 믿을 만한 뉴스를 함께 보시면 좋아요. "
            "아래 원문 포인트를 참고만 해 주세요."
        )
    elif trusted:
        evidence = [EvidenceType.CONFIRMED_FACT, EvidenceType.MARKET_INTERPRETATION]
        confirmed = [primary[:280]]
        confidence = 0.7
        importance = 0.75 if topic == "company" else 0.6
        why = (
            "관련 뉴스·공식 성격의 출처가 있어요. "
            "관심 종목을 보는 분이라면 숫자와 시점까지 함께 확인해 두면 좋아요."
        )
    else:
        evidence = [EvidenceType.MARKET_INTERPRETATION]
        confirmed = []
        confidence = 0.5
        importance = 0.65 if topic == "company" else 0.45
        why = (
            "커뮤니티·소셜에서 포착된 이야기예요. "
            "아직 확인된 소식은 아닐 수 있으니 참고만 해 주세요."
        )

    if len(providers) >= 2 and trusted:
        importance = min(1.0, importance + 0.1)
        confidence = min(1.0, confidence + 0.1)

    # Keep more of the source body for detail reading when LLM is off.
    summary_parts = [t.strip() for t in cluster.texts[:3] if t and t.strip()]
    summary = "\n\n".join(summary_parts) if summary_parts else primary

    title = primary[:80].rstrip(".")
    if len(primary) > 80:
        title += "…"

    now = datetime.utcnow()
    source_at = _source_time(cluster)
    signal = MarketSignal(
        title=title,
        summary=summary,
        why_it_matters=why,
        column_body=_heuristic_column_body(summary, why, key_points, cluster.texts),
        confirmed_facts=confirmed,
        key_points=key_points,
        emphasis={},
        market_reaction=None,
        evidence_mix=evidence,
        content_type=content_type,
        evidence_level=evidence_level,
        importance=importance,
        confidence=confidence,
        related_symbols=symbols,
        related_sectors=sectors,
        category="Macro" if topic == "macro" else "Markets",
        topic=topic,
        participation_suitable=False,
        status=SignalStatus.DRAFT,
        first_seen_at=now,
        updated_at=now,
        published_at=source_at,
        source_urls=list(dict.fromkeys(cluster.urls)),
        providers=providers,
    )
    return sanitize_evidence(
        signal,
        providers,
        source_text="\n".join(cluster.texts),
    )


def _llm_analyze(
    cluster: Cluster, *, universe_symbols: list[str] | None = None
) -> MarketSignal | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        providers = cluster.unique_providers
        joined = "\n---\n".join(
            f"[{item.provider}] {item.text}" for item in cluster.items[:8]
        )
        prompt = SIGNAL_ANALYSIS_PROMPT.format(
            providers=", ".join(providers) or "unknown",
            posts=joined,
        )
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        from app.core.usage import record_llm_usage

        record_llm_usage(resp, stage="analyze", model=settings.openai_model)
        content = resp.choices[0].message.content or ""
        data = json.loads(content)
        evidence = []
        for item in data.get("evidence_mix", []):
            try:
                evidence.append(EvidenceType(item))
            except ValueError:
                continue

        reaction = data.get("market_reaction")
        if reaction in ("null", "None", ""):
            reaction = None

        is_relevant = bool(data.get("is_relevant", True))
        importance = float(data.get("importance") or 0.5)
        confidence = float(data.get("confidence") or 0.5)
        content_type = normalize_content_type(data.get("content_type"))
        evidence_level = normalize_evidence_level(data.get("evidence_level"))
        if not is_relevant:
            importance = min(importance, 0.25)
            confidence = min(confidence, 0.25)

        joined_text = " ".join(cluster.texts)
        fallback_symbols = _resolve_symbols(joined_text, universe_symbols)
        key_points = _clean_points(data.get("key_points"))
        if not key_points:
            key_points = _clean_points(data.get("confirmed_facts")) or [
                t[:280] for t in cluster.texts[:4] if t and t.strip()
            ]
        summary = data.get("summary") or cluster.texts[0]
        why = data.get("why_it_matters") or ""
        column_body = str(data.get("column_body") or "").strip()
        if len(column_body) < 120:
            column_body = _heuristic_column_body(
                summary, why, key_points, cluster.texts
            )
        emphasis = _parse_emphasis(
            data.get("emphasis"),
            summary=summary,
            why=why,
        )
        related_symbols = data.get("related_symbols") or fallback_symbols
        if not related_symbols and is_macro_theme(
            joined_text, settings.macro_keywords()
        ):
            related_symbols = list(settings.macro_index_symbol_list())
        related_sectors = data.get("related_sectors") or _resolve_sectors(
            joined_text, related_symbols or []
        )
        from app.pipeline.industries import normalize_industry_category

        category = normalize_industry_category(data.get("category"))
        if not category:
            # Soft fallback from payload/text cues
            category = normalize_industry_category(
                " ".join(
                    [
                        str(data.get("category") or ""),
                        str(data.get("topic") or ""),
                        " ".join(related_sectors or []),
                    ]
                )
            )
        suitable = bool(data.get("participation_suitable"))
        options_raw = data.get("participation_options") or []
        options: list[str] = []
        if suitable and isinstance(options_raw, list):
            for item in options_raw:
                label = str(item or "").strip()
                if label and label not in options:
                    options.append(label)
            if len(options) < 2:
                suitable = False
                options = []
        ptype = str(data.get("participation_type") or "").strip().lower() or None
        if suitable and ptype not in (
            "binary",
            "choice",
            "sentiment",
            "opinion",
            "prediction",
        ):
            ptype = "binary"
        signal = MarketSignal(
            title=data.get("title") or "이슈",
            summary=summary,
            why_it_matters=why,
            column_body=column_body,
            confirmed_facts=_clean_points(data.get("confirmed_facts")),
            key_points=key_points,
            emphasis=emphasis,
            market_reaction=reaction,
            evidence_mix=evidence or [EvidenceType.MARKET_INTERPRETATION],
            content_type=content_type,
            evidence_level=evidence_level,
            importance=importance,
            confidence=confidence,
            related_symbols=related_symbols,
            related_sectors=related_sectors,
            category=category,
            topic=(str(data.get("topic") or "").strip() or None),
            is_trending=bool(data.get("is_trending")),
            participation_suitable=suitable,
            participation_type=ptype if suitable else None,
            participation_question=(
                (str(data.get("participation_question") or "").strip() or None)
                if suitable
                else None
            ),
            participation_options=options,
            status=SignalStatus.DRAFT,
            published_at=_source_time(cluster),
            source_urls=list(dict.fromkeys(cluster.urls)),
            providers=providers,
        )
        logger.info(
            "llm_analyze ok prompt=%s relevant=%s type=%s level=%s providers=%s size=%s",
            SIGNAL_ANALYSIS_PROMPT_VERSION,
            is_relevant,
            content_type,
            evidence_level,
            providers,
            len(cluster.items),
        )
        return sanitize_evidence(
            signal,
            providers,
            source_text=joined_text,
        )
    except Exception:
        logger.exception("LLM analyze failed; falling back to heuristic")
        return None


def analyze_cluster(
    cluster: Cluster, *, universe_symbols: list[str] | None = None
) -> MarketSignal:
    return _llm_analyze(cluster, universe_symbols=universe_symbols) or _heuristic_analyze(
        cluster, universe_symbols=universe_symbols
    )
