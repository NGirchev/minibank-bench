"""Time helpers. Every instant stored by minibank is timezone-aware UTC."""
from __future__ import annotations

from datetime import datetime, timezone


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    """Start and end of a calendar month, as aware datetimes."""
    ny, nm = _next_month(year, month)
    return datetime(year, month, 1).astimezone(), datetime(ny, nm, 1).astimezone()


def month_bounds_utc(year: int, month: int) -> tuple[datetime, datetime]:
    ny, nm = _next_month(year, month)
    return utc(year, month, 1), utc(ny, nm, 1)


def iso_utc(at: datetime) -> str:
    """'2026-03-31T23:30:00Z'."""
    return at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
