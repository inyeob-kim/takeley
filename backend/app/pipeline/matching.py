"""LLM Issue Match — NEW / UPDATE / REJECT (semantic decision maker).

Deterministic lexical similarity may only shrink shortlists — never final merge.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.core.config import get_settings
from app.pipeline.prompts import ISSUE_MATCH_PROMPT, ISSUE_MATCH_PROMPT_VERSION
from app.pipeline.understanding import UnderstandingResult

logger = logging.getLogger(__name__)

DECISION_NEW = "NEW_ISSUE"
DECISION_UPDATE = "UPDATE_EXISTING"
DECISION_REJECT = "REJECT"


@dataclass(frozen=True)
class ExistingIssueBrief:
    id: str
    title: str
    summary: str = ""
    topic: str = ""
    category: str | None = None


@dataclass(frozen=True)
class MatchDecision:
    decision: str
    existing_issue_id: str | None
    confidence: float
    reason: str
    source: str = "heuristic"  # heuristic | llm


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _sim(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def heuristic_match(
    understanding: UnderstandingResult,
    existing: list[ExistingIssueBrief],
) -> MatchDecision:
    """Testable fallback when no LLM key. Still meaning-ish via topic/event text."""
    if not understanding.is_issue_candidate or understanding.novelty == "opinion_only":
        return MatchDecision(DECISION_REJECT, None, 0.9, "opinion_or_not_candidate", "heuristic")

    cand_blob = " ".join(
        [
            understanding.topic,
            understanding.event,
            understanding.claim,
            " ".join(understanding.entities),
        ]
    )
    best: ExistingIssueBrief | None = None
    best_score = 0.0
    for ex in existing:
        ex_blob = " ".join([ex.topic or "", ex.title or "", ex.summary or ""])
        score = max(
            _sim(understanding.event, ex.title),
            _sim(understanding.event, ex.summary),
            _sim(understanding.topic, ex.topic),
            _sim(cand_blob, ex_blob),
        )
        if score > best_score:
            best_score = score
            best = ex

    # High overlap on event wording → update
    if best and best_score >= 0.72:
        return MatchDecision(
            DECISION_UPDATE, best.id, best_score, "high_event_similarity", "heuristic"
        )
    # Shared entity tokens but low event similarity → new issue (Case B)
    if best and understanding.entities:
        ex_text = _norm(f"{best.title} {best.summary} {best.topic}")
        shared = [
            e for e in understanding.entities if e and _norm(e) in ex_text
        ]
        if shared and best_score < 0.55:
            return MatchDecision(
                DECISION_NEW,
                None,
                0.7,
                f"shared_entity_different_event:{','.join(shared[:3])}",
                "heuristic",
            )
    return MatchDecision(DECISION_NEW, None, 0.6, "no_close_existing", "heuristic")


def match_to_existing(
    understanding: UnderstandingResult,
    existing: list[ExistingIssueBrief],
) -> MatchDecision:
    settings = get_settings()
    if not understanding.is_issue_candidate:
        return MatchDecision(DECISION_REJECT, None, 0.95, "not_candidate", "heuristic")
    if understanding.novelty == "opinion_only":
        return MatchDecision(DECISION_REJECT, None, 0.9, "opinion_only", "heuristic")

    if not settings.openai_api_key:
        return heuristic_match(understanding, existing)

    try:
        from openai import OpenAI

        from app.core.usage import record_llm_usage

        client = OpenAI(api_key=settings.openai_api_key)
        candidate_json = json.dumps(
            {
                "topic": understanding.topic,
                "event": understanding.event,
                "claim": understanding.claim,
                "entities": understanding.entities,
                "novelty": understanding.novelty,
                "relevance": understanding.relevance,
            },
            ensure_ascii=False,
        )
        existing_json = json.dumps(
            [
                {
                    "id": e.id,
                    "title": e.title,
                    "summary": (e.summary or "")[:400],
                    "topic": e.topic,
                    "category": e.category,
                }
                for e in existing
            ],
            ensure_ascii=False,
        )
        prompt = ISSUE_MATCH_PROMPT.format(
            candidate_json=candidate_json,
            existing_json=existing_json or "[]",
        )
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        record_llm_usage(resp, stage="match", model=settings.openai_model)
        data = json.loads(resp.choices[0].message.content or "{}")
        decision = str(data.get("decision") or DECISION_NEW).upper()
        if decision not in {DECISION_NEW, DECISION_UPDATE, DECISION_REJECT}:
            decision = DECISION_NEW
        eid = data.get("existing_issue_id")
        if decision == DECISION_UPDATE and not eid and existing:
            # require id; fall back to heuristic
            return heuristic_match(understanding, existing)
        return MatchDecision(
            decision,
            str(eid) if eid else None,
            float(data.get("confidence") or 0.0),
            str(data.get("reason") or "")[:240],
            "llm",
        )
    except Exception:
        logger.exception(
            "match llm failed version=%s; heuristic fallback",
            ISSUE_MATCH_PROMPT_VERSION,
        )
        return heuristic_match(understanding, existing)
