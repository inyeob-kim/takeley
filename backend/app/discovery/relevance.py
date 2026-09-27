"""Cheap keep/drop for discovery items. Not an Issue quality gate."""

from __future__ import annotations

from app.domain.models import RawItem

# Politics / economy / finance / tech / world — TAKELEY Issue lanes, not fame.
_KEEP = (
    "대통령",
    "국회",
    "정부",
    "여당",
    "야당",
    "선거",
    "관세",
    "정책",
    "법원",
    "판결",
    "제재",
    "물가",
    "금리",
    "환율",
    "부동산",
    "한국은행",
    "공시",
    "실적",
    "파산",
    "반도체",
    "전쟁",
    "휴전",
    "외교",
    "북한",
    "중국",
    "파업",
    "규제",
    "trump",
    "election",
    "congress",
    "white house",
    "tariff",
    "fed",
    "federal reserve",
    "inflation",
    "recession",
    "interest rate",
    "cpi",
    "unemployment",
    "earnings",
    "bankruptcy",
    "sec ",
    "ipo",
    "semiconductor",
    "ukraine",
    "israel",
    "nato",
    "sanction",
    "strike",
    "openai",
    "antitrust",
)

_DROP = (
    "배드민턴",
    "아시안게임",
    "프로야구",
    "k리그",
    "아이돌",
    "연예",
    "드라마",
    "예능",
    "mlb",
    "nba",
    "nfl",
    "premier league",
    "box office",
    "netflix",
    "season 4",
    "season 3",
    "trailer",
    "celebrity",
    "k-pop",
    "kpop",
)


def is_issue_relevant(*parts: str) -> bool:
    blob = " ".join(p for p in parts if p).lower()
    if not blob.strip():
        return False
    if any(marker in blob for marker in _KEEP):
        return True
    if any(marker in blob for marker in _DROP):
        return False
    return False


def filter_issue_relevant(items: list[RawItem]) -> list[RawItem]:
    kept: list[RawItem] = []
    for item in items:
        if is_issue_relevant(item.title or "", item.text or ""):
            kept.append(item)
    return kept
