"""LLM Understanding — semantic read of a candidate (not Issue publish)."""

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

_OPINION_RE = re.compile(
    r"\b(i think|i believe|imo|in my opinion|내가 보기에|개인적으로)\b",
    re.I,
)


@dataclass
class UnderstandingResult:
    is_issue_candidate: bool
    relevance: float = 0.0
    topic: str = ""
    event: str = ""
    claim: str = ""
    entities: list[str] = field(default_factory=list)
    novelty: str = "new_development"
    participation_suitable_hint: bool = False
    raw_id: str = ""
    text: str = ""
    provider: str = ""
    source: str = "heuristic"  # heuristic | llm


def _heuristic_understand(
    *,
    text: str,
    provider: str,
    raw_id: str = "",
) -> UnderstandingResult:
    cleaned = (text or "").strip()
    if len(cleaned) < 12:
        return UnderstandingResult(
            False, 0.0, novelty="opinion_only", raw_id=raw_id, text=cleaned, provider=provider
        )
    if _OPINION_RE.search(cleaned) and not re.search(
        r"\b(announce|announced|reports?|delay|launch|filed|ruling)\b", cleaned, re.I
    ):
        return UnderstandingResult(
            False,
            0.2,
            topic="opinion",
            event="",
            novelty="opinion_only",
            raw_id=raw_id,
            text=cleaned,
            provider=provider,
        )
    # crude topic = first ~8 words
    words = re.findall(r"[A-Za-z0-9\-\.]+", cleaned)
    topic = " ".join(words[:8]) if words else cleaned[:40]
    return UnderstandingResult(
        True,
        0.65,
        topic=topic,
        event=cleaned[:160],
        claim=cleaned[:160],
        entities=words[:5],
        novelty="new_development",
        participation_suitable_hint=bool(
            re.search(r"\b(will|should|demand|debate|vs)\b", cleaned, re.I)
        ),
        raw_id=raw_id,
        text=cleaned,
        provider=provider,
        source="heuristic",
    )


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
        return UnderstandingResult(
            is_issue_candidate=bool(data.get("is_issue_candidate", False)),
            relevance=float(data.get("relevance") or 0.0),
            topic=str(data.get("topic") or "")[:120],
            event=str(data.get("event") or "")[:280],
            claim=str(data.get("claim") or "")[:280],
            entities=[str(e)[:64] for e in entities[:12]],
            novelty=str(data.get("novelty") or "new_development")[:64],
            participation_suitable_hint=bool(
                data.get("participation_suitable_hint", False)
            ),
            raw_id=raw_id,
            text=text,
            provider=provider,
            source="llm",
        )
    except Exception:
        logger.exception(
            "understanding llm failed version=%s; heuristic fallback",
            ISSUE_UNDERSTANDING_PROMPT_VERSION,
        )
        return _heuristic_understand(text=text, provider=provider, raw_id=raw_id)


# Expose for tests
heuristic_understand = _heuristic_understand
