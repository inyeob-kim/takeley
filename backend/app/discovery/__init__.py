"""Source-module discovery: registry + run results. Providers stay in app.providers."""

from app.discovery.expire import expire_stale_rss_items
from app.discovery.protocol import IngestContext, ModuleRunResult
from app.discovery.registry import run_enabled_modules

__all__ = [
    "IngestContext",
    "ModuleRunResult",
    "expire_stale_rss_items",
    "run_enabled_modules",
]
