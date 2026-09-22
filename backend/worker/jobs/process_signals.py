"""Process raw_items → Issues (candidate → LLM understand → match → card).

Legacy finance Signal V1 path removed. Bootstrap/focus still call this entrypoint.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from worker.jobs.process_issues_v2 import run_process_issues_v2

logger = logging.getLogger(__name__)


def run_process_signals(
    db: Session,
    limit: int = 100,
    *,
    focus_symbols: list[str] | None = None,
    bootstrap: bool = False,
) -> dict:
    """Common Intelligence process entry — Issue pipeline only."""
    if focus_symbols or bootstrap:
        logger.info(
            "process focus/bootstrap symbols=%s bootstrap=%s (still Issue pipeline)",
            focus_symbols,
            bootstrap,
        )
    return run_process_issues_v2(db, limit=limit)
