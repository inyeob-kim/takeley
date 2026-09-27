"""X discovery module — wrapper around existing ingest helpers. No search rewrite."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.discovery.protocol import IngestContext, ModuleRunResult


class XSourceModule:
    module_id = "x"

    def run(self, db: Session, ctx: IngestContext) -> ModuleRunResult:
        from worker.jobs.ingest import run_x_ingest

        fetched, inserted = run_x_ingest(db, ctx)
        return ModuleRunResult(fetched=fetched, inserted=inserted)
