from __future__ import annotations


def classify_topic(text: str) -> str:
    lowered = text.lower()
    if any(
        k in lowered
        for k in (
            "rate",
            "fed",
            "fomc",
            "cpi",
            "inflation",
            "jobs",
            "oil",
            "crude",
            "trump",
            "tariff",
            "treasury",
            "yield",
        )
    ):
        return "macro"
    if any(
        k in lowered
        for k in (
            "earnings",
            "guidance",
            "delivery",
            "production",
            "margin",
            "recall",
            "acquisition",
            "buyback",
        )
    ):
        return "company"
    if any(k in lowered for k in ("rumor", "allegedly", "unverified", "sources say")):
        return "speculation"
    return "general"
