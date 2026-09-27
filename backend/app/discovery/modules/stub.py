"""Disabled-by-default placeholder. Fetch happens only after a real Provider exists."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.discovery.protocol import IngestContext, ModuleRunResult


class StubSourceModule:
    def __init__(self, module_id: str):
        self.module_id = module_id

    def run(self, db: Session, ctx: IngestContext) -> ModuleRunResult:
        return ModuleRunResult(skipped_reason="not_implemented")
