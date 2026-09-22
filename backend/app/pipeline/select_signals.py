"""LLM (or rule) selection of personalized signals from the common pool."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from app.core.config import get_settings
from app.pipeline.classification import (
    is_confirmed_user_label,
    is_home_excluded_content,
)
from app.pipeline.prompts import (
    PERSONAL_SIGNAL_SELECT_PROMPT,
    PERSONAL_SIGNAL_SELECT_PROMPT_VERSION,
)
from app.schemas import SignalOut

logger = logging.getLogger(__name__)


@dataclass
class SelectedSignal:
    signal: SignalOut
    section: str
    reason: str


def _candidate_card(signal: SignalOut) -> dict:
    return {
        "signal_id": signal.id,
        "title": signal.title,
        "summary": (signal.summary or "")[:280],
        "why_it_matters": (signal.why_it_matters or "")[:160],
        "related_symbols": signal.related_symbols,
        "related_sectors": signal.related_sectors,
        "evidence_mix": signal.evidence_mix,
        "content_type": getattr(signal, "content_type", None) or "REPORT",
        "evidence_level": getattr(signal, "evidence_level", None) or "UNVERIFIED",
        "importance": signal.importance,
        "confidence": signal.confidence,
    }


def rule_select_signals(
    candidates: list[SignalOut],
    *,
    watchlist_symbols: list[str],
    slot_count: int,
) -> list[SelectedSignal]:
    symbols = {s.upper() for s in watchlist_symbols}
    ranked: list[tuple[float, SignalOut]] = []
    for row in candidates:
        if is_home_excluded_content(getattr(row, "content_type", None)):
            continue
        related = {x.upper() for x in (row.related_symbols or [])}
        confirmed = (
            2.0
            if is_confirmed_user_label(getattr(row, "evidence_level", None))
            else 0.0
        )
        score = len(symbols & related) * 2 + confirmed + float(row.importance or 0)
        ranked.append((score, row))
    ranked.sort(key=lambda x: x[0], reverse=True)

    selected: list[SelectedSignal] = []
    for score, row in ranked[:slot_count]:
        related = {x.upper() for x in (row.related_symbols or [])}
        section = "watchlist" if symbols & related else "macro"
        selected.append(
            SelectedSignal(
                signal=row,
                section=section,
                reason="규칙 랭킹으로 선정",
            )
        )
    return selected


def llm_select_signals(
    candidates: list[SignalOut],
    *,
    watchlist_symbols: list[str],
    slot_count: int | None = None,
    user_id: str | None = None,
) -> list[SelectedSignal] | None:
    settings = get_settings()
    slot_count = slot_count or settings.brief_slot_count
    if not candidates:
        return []
    if not settings.openai_api_key:
        return None

    allow = {c.id: c for c in candidates}
    prompt = PERSONAL_SIGNAL_SELECT_PROMPT.format(
        symbols=", ".join(watchlist_symbols) or "관심 종목 없음 (시장 전반)",
        slot_count=slot_count,
        candidates_json=json.dumps(
            [_candidate_card(c) for c in candidates],
            ensure_ascii=False,
        ),
    )
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        from app.core.usage import record_llm_usage

        record_llm_usage(
            resp,
            stage="select",
            model=settings.openai_model,
            user_id=user_id,
        )
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)
        raw_selected = data.get("selected") or []
        out: list[SelectedSignal] = []
        seen: set[str] = set()
        for item in raw_selected:
            if not isinstance(item, dict):
                continue
            sid = str(item.get("signal_id") or "")
            if sid not in allow or sid in seen:
                continue
            section = str(item.get("section") or "watchlist")
            if section not in ("macro", "watchlist"):
                section = "watchlist"
            out.append(
                SelectedSignal(
                    signal=allow[sid],
                    section=section,
                    reason=str(item.get("reason") or ""),
                )
            )
            seen.add(sid)
            if len(out) >= slot_count:
                break
        logger.info(
            "llm_select ok prompt=%s candidates=%s selected=%s",
            PERSONAL_SIGNAL_SELECT_PROMPT_VERSION,
            len(candidates),
            len(out),
        )
        return out
    except Exception:
        logger.exception("LLM signal select failed")
        return None


def select_personal_signals(
    candidates: list[SignalOut],
    *,
    watchlist_symbols: list[str],
    slot_count: int | None = None,
    user_id: str | None = None,
) -> list[SelectedSignal]:
    settings = get_settings()
    slot_count = slot_count or settings.brief_slot_count
    selected = llm_select_signals(
        candidates,
        watchlist_symbols=watchlist_symbols,
        slot_count=slot_count,
        user_id=user_id,
    )
    if selected is None:
        return rule_select_signals(
            candidates,
            watchlist_symbols=watchlist_symbols,
            slot_count=slot_count,
        )
    if not selected and candidates:
        return rule_select_signals(
            candidates,
            watchlist_symbols=watchlist_symbols,
            slot_count=slot_count,
        )
    return selected
