from datetime import datetime, timedelta
from typing import Dict, List


class AccountScheduler:
    """
    Priority scheduler for account polling.
    - tier1: every 3 minutes
    - tier2: every 8 minutes
    """

    def __init__(self, tier1_accounts: List[str], tier2_accounts: List[str]) -> None:
        self.intervals_seconds: Dict[str, int] = {}
        self.next_fetch_time: Dict[str, datetime] = {}

        now = datetime.now()
        for account in tier1_accounts:
            self.intervals_seconds[account] = 3 * 60
            self.next_fetch_time[account] = now

        for account in tier2_accounts:
            self.intervals_seconds[account] = 8 * 60
            self.next_fetch_time[account] = now

    def due_accounts(self, now: datetime | None = None) -> List[str]:
        now = now or datetime.now()
        due = [u for u, due_time in self.next_fetch_time.items() if now >= due_time]
        return sorted(due)

    def mark_fetched(self, username: str, defer_minutes: int | None = None, now: datetime | None = None) -> None:
        now = now or datetime.now()
        if defer_minutes is not None:
            self.next_fetch_time[username] = now + timedelta(minutes=defer_minutes)
            return
        interval = self.intervals_seconds.get(username, 8 * 60)
        self.next_fetch_time[username] = now + timedelta(seconds=interval)
