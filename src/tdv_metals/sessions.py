"""Independent exchange calendar and indicative regional-session context.

Weekly windows are expressed in the named IANA time zone. ``weekday`` is the
local *start* day (Monday=0). An end time at or before the start time is on
the next local day. Date exceptions apply to the local calendar date they name,
including the portion of an overnight window after midnight.

This module does not obtain data from Market 24h. Its contextual session labels
must be supplied by the caller and are never used as proof that a futures
contract is tradable. Exchange schedules should be checked against the venue's
current, instrument-specific published calendar before paper trading.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_CLOCK_RE = re.compile(r"^\d{2}:\d{2}$")


def _clock(value: str) -> time:
    if not isinstance(value, str) or not _CLOCK_RE.fullmatch(value):
        raise ValueError("clock time must use HH:MM in 24-hour format")
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid clock time: {value}") from exc


def _date(value: str) -> date:
    if not isinstance(value, str):
        raise TypeError("date must use YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid date: {value}") from exc
    if parsed.isoformat() != value:
        raise ValueError("date must use YYYY-MM-DD")
    return parsed


def _zone(value: str) -> ZoneInfo:
    if not isinstance(value, str) or not value:
        raise ValueError("timezone must be an IANA zone name")
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown IANA timezone: {value}") from exc


@dataclass(frozen=True)
class WeeklyWindow:
    weekday: int
    start: str
    end: str
    label: str = "regular"

    def __post_init__(self) -> None:
        if type(self.weekday) is not int or not 0 <= self.weekday <= 6:
            raise ValueError("weekday must be an integer from 0 (Monday) to 6 (Sunday)")
        _clock(self.start)
        _clock(self.end)
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("window label must be nonempty")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> WeeklyWindow:
        return cls(
            weekday=value["weekday"],
            start=value["start"],
            end=value["end"],
            label=value.get("label", "regular"),
        )


@dataclass(frozen=True)
class EarlyClose:
    date: str
    time: str

    def __post_init__(self) -> None:
        _date(self.date)
        _clock(self.time)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> EarlyClose:
        return cls(date=value["date"], time=value["time"])


@dataclass(frozen=True)
class CalendarConfig:
    name: str
    timezone: str
    windows: tuple[WeeklyWindow, ...]
    closed_dates: tuple[str, ...] = ()
    early_closes: tuple[EarlyClose, ...] = ()
    source: str = "user-configured"
    source_url: str | None = None
    verified: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("calendar name must be nonempty")
        _zone(self.timezone)
        if not self.windows or not all(isinstance(w, WeeklyWindow) for w in self.windows):
            raise ValueError("calendar must have at least one valid weekly window")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("calendar source must be nonempty")
        if not isinstance(self.verified, bool):
            raise TypeError("verified must be boolean")
        if self.source_url is not None and not self.source_url.startswith(("https://", "http://")):
            raise ValueError("source_url must be an HTTP(S) URL")
        if self.verified and self.source_url is None:
            raise ValueError("verified exchange calendars require a source_url")
        closed = [_date(day) for day in self.closed_dates]
        if len(closed) != len(set(closed)):
            raise ValueError("closed_dates contains duplicates")
        if not all(isinstance(item, EarlyClose) for item in self.early_closes):
            raise ValueError("early_closes must contain EarlyClose values")
        dates = [item.date for item in self.early_closes]
        if len(dates) != len(set(dates)):
            raise ValueError("early_closes contains duplicate dates")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> CalendarConfig:
        return cls(
            name=value["name"],
            timezone=value["timezone"],
            windows=tuple(WeeklyWindow.from_dict(item) for item in value["windows"]),
            closed_dates=tuple(value.get("closed_dates", ())),
            early_closes=tuple(EarlyClose.from_dict(item) for item in value.get("early_closes", ())),
            source=value.get("source", "user-configured"),
            source_url=value.get("source_url"),
            verified=value.get("verified", False),
        )


@dataclass(frozen=True)
class ContextConfig:
    """Indicative regional trading hours; never an instrument eligibility rule."""

    name: str
    timezone: str
    windows: tuple[WeeklyWindow, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("context name must be nonempty")
        _zone(self.timezone)
        if not self.windows or not all(isinstance(w, WeeklyWindow) for w in self.windows):
            raise ValueError("context must have at least one valid weekly window")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ContextConfig:
        return cls(
            name=value["name"],
            timezone=value["timezone"],
            windows=tuple(WeeklyWindow.from_dict(item) for item in value["windows"]),
        )


def _local_boundary(day: date, clock: time, zone: ZoneInfo) -> datetime:
    """Resolve a wall time, rejecting a nonexistent DST clock time."""
    local = datetime.combine(day, clock, tzinfo=zone)
    utc = local.astimezone(timezone.utc)
    if utc.astimezone(zone).replace(tzinfo=None) != local.replace(tzinfo=None):
        raise ValueError(f"nonexistent local clock time {day} {clock} in {zone.key}")
    return utc


def _raw_intervals(
    windows: Sequence[WeeklyWindow], zone: ZoneInfo, first_day: date, last_day: date
) -> list[tuple[datetime, datetime, str]]:
    intervals: list[tuple[datetime, datetime, str]] = []
    day = first_day - timedelta(days=1)  # overnight window begun yesterday
    while day <= last_day:
        for window in windows:
            if day.weekday() != window.weekday:
                continue
            start_clock, end_clock = _clock(window.start), _clock(window.end)
            end_day = day + timedelta(days=1 if end_clock <= start_clock else 0)
            start = _local_boundary(day, start_clock, zone)
            end = _local_boundary(end_day, end_clock, zone)
            if end <= start:
                raise ValueError("window end must follow start in absolute time")
            intervals.append((start, end, window.label))
        day += timedelta(days=1)
    return intervals


def _exchange_intervals(
    calendar: CalendarConfig, first_day: date, last_day: date
) -> list[tuple[datetime, datetime, str]]:
    zone = _zone(calendar.timezone)
    closed = set(calendar.closed_dates)
    early = {item.date: _clock(item.time) for item in calendar.early_closes}
    output: list[tuple[datetime, datetime, str]] = []
    for start, end, label in _raw_intervals(calendar.windows, zone, first_day, last_day):
        cursor = start
        while cursor < end:
            local_day = cursor.astimezone(zone).date()
            next_midnight = _local_boundary(local_day + timedelta(days=1), time(0), zone)
            segment_end = min(end, next_midnight)
            key = local_day.isoformat()
            if key not in closed:
                if key in early:
                    cutoff = _local_boundary(local_day, early[key], zone)
                    segment_end = min(segment_end, cutoff)
                if segment_end > cursor:
                    output.append((cursor, segment_end, label))
            cursor = min(end, next_midnight)
    return output


def _merged(
    intervals: Sequence[tuple[datetime, datetime, str]],
) -> list[tuple[datetime, datetime, str]]:
    merged: list[tuple[datetime, datetime, str]] = []
    for start, end, label in sorted(intervals, key=lambda item: (item[0], item[1])):
        if merged and start <= merged[-1][1]:
            previous_start, previous_end, previous_label = merged[-1]
            merged[-1] = (previous_start, max(previous_end, end), previous_label)
        else:
            merged.append((start, end, label))
    return merged


def _context_active(as_of: datetime, item: ContextConfig) -> bool:
    zone = _zone(item.timezone)
    local_day = as_of.astimezone(zone).date()
    intervals = _raw_intervals(item.windows, zone, local_day - timedelta(days=1), local_day)
    return any(start <= as_of < end for start, end, _ in intervals)


def session_status(
    as_of: datetime,
    calendar: CalendarConfig | Mapping[str, Any],
    contexts: Sequence[ContextConfig | Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Return JSON-ready exchange availability and optional indicative context.

    ``as_of`` must be timezone aware. All output instants use UTC ISO 8601.
    Exchange status uses the caller's verified schedule; contextual regional
    sessions have no effect on it. Future dated exceptions are considered when
    finding the next transition.
    """
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone aware")
    now = as_of.astimezone(timezone.utc)
    if isinstance(calendar, Mapping):
        calendar = CalendarConfig.from_dict(calendar)
    if not isinstance(calendar, CalendarConfig):
        raise TypeError("calendar must be CalendarConfig or a mapping")
    zone = _zone(calendar.timezone)
    local_day = now.astimezone(zone).date()

    # A normal weekly cycle has a transition within two weeks. Extend to any
    # later configured closure, which can interrupt an otherwise 24-hour cycle.
    last_day = local_day + timedelta(days=15)
    for exception_day in (*calendar.closed_dates, *(item.date for item in calendar.early_closes)):
        day = _date(exception_day)
        if day >= local_day:
            last_day = max(last_day, day + timedelta(days=8))
    intervals = _merged(_exchange_intervals(calendar, local_day - timedelta(days=1), last_day))
    current = next(((start, end, label) for start, end, label in intervals if start <= now < end), None)
    is_open = current is not None
    if current is not None:
        transition = current[1]
    else:
        transition = next((start for start, _, _ in intervals if start > now), None)
    transition_kind = ("CLOSE" if is_open else "OPEN") if transition is not None else None

    context_items = [ContextConfig.from_dict(item) if isinstance(item, Mapping) else item for item in contexts]
    if not all(isinstance(item, ContextConfig) for item in context_items):
        raise TypeError("contexts must contain ContextConfig values or mappings")
    active = [item.name for item in context_items if _context_active(now, item)]

    return {
        "as_of_utc": now.isoformat(),
        "exchange": calendar.name,
        "exchange_timezone": calendar.timezone,
        "status": "OPEN" if is_open else "CLOSED",
        "is_open": is_open,
        "current_window": current[2] if current else None,
        "next_transition_utc": transition.isoformat() if transition else None,
        "next_transition_kind": transition_kind,
        "seconds_to_transition": int((transition - now).total_seconds()) if transition else None,
        "provenance": {"source": calendar.source, "source_url": calendar.source_url,
                       "verified": calendar.verified},
        "context": {
            "active": active,
            "overlap": len(active) > 1,
            "label": " / ".join(active) if active else "No configured regional session active",
            "note": "Indicative regional context only; exchange calendar controls eligibility.",
        },
    }
