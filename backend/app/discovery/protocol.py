"""Discovery module contract. Separate from SourceProvider.fetch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from app.db.repositories import CursorRepository, RawItemRepository
from app.services.universe import UniverseSymbol


@dataclass
class IngestContext:
    raw_repo: RawItemRepository
    cursor_repo: CursorRepository
    universe: list[UniverseSymbol]
    us_universe: list[UniverseSymbol]
    kr_universe: list[UniverseSymbol]


@dataclass
class ModuleRunResult:
    fetched: int = 0
    inserted: int = 0
    duplicate: int = 0
    failed: int = 0
    error: str | None = None
    skipped_reason: str | None = None
    elapsed_ms: int | None = None


class DiscoveryModule(Protocol):
    module_id: str

    def run(self, db: Session, ctx: IngestContext) -> ModuleRunResult: ...
