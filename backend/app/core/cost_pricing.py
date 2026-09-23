"""Pricing configuration for estimated cost (never invent provider rates)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class PriceStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    CONFIG_REQUIRED = "CONFIG_REQUIRED"
    CONFIGURED = "CONFIGURED"


@dataclass(frozen=True)
class UnitPrice:
    """USD price per unit when configured; otherwise status only."""

    unit: str
    status: PriceStatus
    usd_per_unit: float | None = None
    note: str = ""

    def estimate(self, units: float) -> dict[str, Any]:
        if self.status != PriceStatus.CONFIGURED or self.usd_per_unit is None:
            return {
                "units": units,
                "unit": self.unit,
                "estimated_usd": None,
                "price_status": self.status.value,
                "note": self.note or "Set COST_* env to enable estimates",
            }
        return {
            "units": units,
            "unit": self.unit,
            "estimated_usd": round(units * self.usd_per_unit, 6),
            "price_status": self.status.value,
            "usd_per_unit": self.usd_per_unit,
            "note": self.note,
        }


class CostPricingSettings(BaseSettings):
    """
    Optional USD rates. Empty → CONFIG_REQUIRED (no invented prices).

    Example (do not commit real secrets; rates are public list prices):
      COST_LLM_INPUT_USD_PER_1M=0.15
      COST_LLM_OUTPUT_USD_PER_1M=0.60
      COST_TTS_USD_PER_1M_CHARS=15.0
      COST_X_USD_PER_REQUEST=  # leave empty if plan is flat monthly
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenAI-style: USD per 1M tokens / 1M characters
    cost_llm_input_usd_per_1m: float | None = None
    cost_llm_output_usd_per_1m: float | None = None
    cost_tts_usd_per_1m_chars: float | None = None
    # X is often a flat monthly plan — per-request rate optional.
    # Pay-per-use bills posts returned, not HTTP calls.
    cost_x_usd_per_request: float | None = None
    cost_x_usd_per_post: float | None = None
    cost_x_usd_per_user: float | None = None
    cost_finnhub_usd_per_request: float | None = None
    # Free HTTP (RSS / calendar / Yahoo / article HTML)
    cost_http_usd_per_request: float | None = None


@lru_cache
def get_cost_pricing_settings() -> CostPricingSettings:
    return CostPricingSettings()


def _per_million(rate: float | None, unit: str, note: str) -> UnitPrice:
    if rate is None:
        return UnitPrice(unit=unit, status=PriceStatus.CONFIG_REQUIRED, note=note)
    return UnitPrice(
        unit=unit,
        status=PriceStatus.CONFIGURED,
        usd_per_unit=rate / 1_000_000.0,
        note=note,
    )


def _per_request(rate: float | None, unit: str, note: str) -> UnitPrice:
    if rate is None:
        return UnitPrice(unit=unit, status=PriceStatus.CONFIG_REQUIRED, note=note)
    return UnitPrice(
        unit=unit, status=PriceStatus.CONFIGURED, usd_per_unit=rate, note=note
    )


def pricing_table() -> dict[str, UnitPrice]:
    s = get_cost_pricing_settings()
    return {
        "llm_input_tokens": _per_million(
            s.cost_llm_input_usd_per_1m,
            "token",
            "COST_LLM_INPUT_USD_PER_1M",
        ),
        "llm_output_tokens": _per_million(
            s.cost_llm_output_usd_per_1m,
            "token",
            "COST_LLM_OUTPUT_USD_PER_1M",
        ),
        "tts_characters": _per_million(
            s.cost_tts_usd_per_1m_chars,
            "character",
            "COST_TTS_USD_PER_1M_CHARS",
        ),
        "x_api_requests": _per_request(
            s.cost_x_usd_per_request,
            "request",
            "COST_X_USD_PER_REQUEST (or use flat plan outside this model)",
        ),
        "x_posts": _per_request(
            s.cost_x_usd_per_post,
            "post",
            "COST_X_USD_PER_POST",
        ),
        "x_user_lookups": _per_request(
            s.cost_x_usd_per_user,
            "user",
            "COST_X_USD_PER_USER",
        ),
        "finnhub_requests": _per_request(
            s.cost_finnhub_usd_per_request,
            "request",
            "COST_FINNHUB_USD_PER_REQUEST",
        ),
        "http_requests": _per_request(
            s.cost_http_usd_per_request,
            "request",
            "COST_HTTP_USD_PER_REQUEST (RSS/calendar/article; usually 0)",
        ),
    }


def estimate_line(metric_key: str, units: float) -> dict[str, Any]:
    table = pricing_table()
    price = table.get(metric_key)
    if price is None:
        return {
            "units": units,
            "estimated_usd": None,
            "price_status": PriceStatus.UNKNOWN.value,
            "note": f"No pricing key for {metric_key}",
        }
    return price.estimate(units)
