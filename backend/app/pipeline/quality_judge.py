"""Optional second LLM quality judge after Issue card structuring."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from app.core.config import get_settings
from app.domain.models import MarketSignal, SignalStatus

logger = logging.getLogger(__name__)

JUDGE_PROMPT = """
You are a quality judge for one Issue card. Accept only if:
- title/summary describe a real event or consequential claim (not empty spam)
- not a tipster BUY/PROMOTION
- facts are not obviously invented beyond the evidence sketch
- participation options make sense IF participation_suitable is true

Evidence sketch:
{evidence}

Issue JSON:
{issue_json}

Return ONLY JSON:
{{"accept": true, "reason": "short"}}
""".strip()


@dataclass(frozen=True)
class JudgeDecision:
    accepted: bool
    reason: str
    source: str  # skipped | heuristic | llm


def _heuristic_judge(signal: MarketSignal) -> JudgeDecision:
    title = (signal.title or "").strip()
    summary = (signal.summary or "").strip()
    if len(title) < 4 or len(summary) < 8:
        return JudgeDecision(False, "too_short", "heuristic")
    ct = (signal.content_type or "").upper()
    if ct in {"INVESTMENT_CALL", "PROMOTION"}:
        return JudgeDecision(False, "tipster_or_promo", "heuristic")
    return JudgeDecision(True, "ok", "heuristic")


def judge_issue_card(
    signal: MarketSignal,
    *,
    evidence_text: str = "",
) -> JudgeDecision:
    settings = get_settings()
    if not settings.issue_llm_quality_judge_enabled:
        return JudgeDecision(True, "judge_disabled", "skipped")

    base = _heuristic_judge(signal)
    if not base.accepted:
        signal.status = SignalStatus.REJECTED
        return base

    if not settings.openai_api_key:
        return base

    try:
        from openai import OpenAI

        from app.core.usage import record_llm_usage

        client = OpenAI(api_key=settings.openai_api_key)
        issue_json = json.dumps(
            {
                "title": signal.title,
                "summary": signal.summary,
                "content_type": signal.content_type,
                "participation_suitable": signal.participation_suitable,
                "participation_options": signal.participation_options,
                "confirmed_facts": signal.confirmed_facts,
            },
            ensure_ascii=False,
        )
        prompt = JUDGE_PROMPT.format(
            evidence=(evidence_text or "")[:3000],
            issue_json=issue_json,
        )
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        record_llm_usage(resp, stage="quality_judge", model=settings.openai_model)
        data = json.loads(resp.choices[0].message.content or "{}")
        ok = bool(data.get("accept", True))
        reason = str(data.get("reason") or ("ok" if ok else "rejected"))[:200]
        if not ok:
            signal.status = SignalStatus.REJECTED
        return JudgeDecision(ok, reason, "llm")
    except Exception:
        logger.exception("quality judge llm failed; keep heuristic accept")
        return base
