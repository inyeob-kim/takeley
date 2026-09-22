"""Optional embeddings for Match shortlist assist — NOT final same-Issue judge."""

from __future__ import annotations

import logging
import math

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


def embed_texts(texts: list[str]) -> list[list[float] | None]:
    """Return embedding vectors or Nones if unavailable."""
    settings = get_settings()
    if not settings.issue_embedding_enabled or not settings.openai_api_key:
        return [None] * len(texts)
    clean = [(t or "")[:2000] for t in texts]
    if not any(clean):
        return [None] * len(texts)
    try:
        from openai import OpenAI

        from app.core.usage import record_usage

        client = OpenAI(api_key=settings.openai_api_key)
        model = settings.issue_embedding_model
        resp = client.embeddings.create(model=model, input=clean)
        record_usage(
            "embedding_requests",
            1,
            tags={"model": model, "n": str(len(clean))},
            scope_type="shared",
        )
        by_idx = {item.index: item.embedding for item in resp.data}
        return [list(by_idx[i]) if i in by_idx else None for i in range(len(clean))]
    except Exception:
        logger.exception("embed_texts failed")
        return [None] * len(texts)


def rank_ids_by_embedding(
    query_text: str,
    id_text_pairs: list[tuple[str, str]],
    *,
    top_k: int,
) -> list[str]:
    """
    Reorder existing Issue ids by embedding similarity to query.
    Assists shortlist only — Match LLM still decides NEW/UPDATE/REJECT.
    """
    if not id_text_pairs:
        return []
    top_k = max(1, top_k)
    texts = [query_text] + [t for _, t in id_text_pairs]
    vectors = embed_texts(texts)
    q = vectors[0]
    if q is None:
        return [i for i, _ in id_text_pairs[:top_k]]
    scored: list[tuple[float, str]] = []
    for idx, (oid, _) in enumerate(id_text_pairs):
        v = vectors[idx + 1]
        scored.append((_cosine(q, v) if v else 0.0, oid))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [oid for _, oid in scored[:top_k]]
