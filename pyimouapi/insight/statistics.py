"""getAlarmMessageStatistics parsing and briefing text."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

_LABEL_NAMES = {
    "humanAlarm": "Person",
    "carAlarm": "Vehicle",
    "petAlarm": "Pet",
    "packageAlarm": "Package",
    "motionAlarm": "Motion",
    "faceAlarm": "Face",
}
_CODE_KEYS = ("labelType", "label", "labelName", "name", "code", "type")
_COUNT_KEYS = ("count", "num", "total", "value")
_DETECTION_KEYS = ("elderly", "package", "child", "pet", "doorway")
_HOUR_INTERVAL = 2


@dataclass(frozen=True, slots=True)
class IdentifiedEvent:
    """One AI label and how many times it was seen."""

    code: str
    count: int


@dataclass(frozen=True, slots=True)
class RiskWindow:
    """One risk period and the sentence that describes it."""

    date: str
    start_hour: str
    end_hour: str
    count: int
    text: str


@dataclass(frozen=True, slots=True)
class LabelTiming:
    """Sample times and two-hour counts for one message type."""

    label: str
    times: tuple[str, ...]
    buckets: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class DailyAlarmRollup:
    """One row from the statistics array."""

    date: str
    total: int
    human: int
    vehicle: int
    pet: int
    package: int
    events: tuple[IdentifiedEvent, ...] = ()
    risks: tuple[RiskWindow, ...] = ()
    timings: tuple[LabelTiming, ...] = ()


@dataclass(frozen=True, slots=True)
class InsightBriefing:
    """Parsed statistics API payload."""

    daily: tuple[DailyAlarmRollup, ...]
    risk_notes: tuple[str, ...]


def detection_totals(events: tuple[IdentifiedEvent, ...]) -> dict[str, int]:
    """Fold label codes into the five groups shown on the daily screen."""
    totals = dict.fromkeys(_DETECTION_KEYS, 0)
    for event in events:
        key = _detection_key(event.code)
        if key is not None:
            totals[key] += event.count
    return totals


def _detection_key(code: str) -> str | None:
    text = code.lower().replace("-", "_")
    if any(word in text for word in ("elderly", "old_man", "oldman", "老人")):
        return "elderly"
    if any(word in text for word in ("package", "parcel", "包裹")):
        return "package"
    if any(word in text for word in ("child", "kid", "儿童")):
        return "child"
    if any(word in text for word in ("pet", "animal", "宠物")):
        return "pet"
    if any(
        word in text
        for word in ("door", "entrance", "gate", "门口", "loiter", "stayover")
    ):
        return "doorway"
    return None


def _int_field(row: dict[str, Any], *keys: str) -> int:
    for key in keys:
        if key not in row or row[key] is None:
            continue
        try:
            return int(row[key])
        except (TypeError, ValueError):
            return 0
    return 0


def _count_or_one(raw: dict[str, Any]) -> int:
    """Use an explicit count, including zero. A bare label counts as one."""
    for key in _COUNT_KEYS:
        if key not in raw or raw[key] is None:
            continue
        try:
            return int(raw[key])
        except (TypeError, ValueError):
            return 0
    return 1


def _label_pairs(raw: Any) -> list[tuple[str, int]]:
    """Read label/count pairs from a list, a map, or a JSON string."""
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        try:
            return _label_pairs(json.loads(text))
        except json.JSONDecodeError:
            return [(text, 1)]
    if isinstance(raw, list):
        pairs: list[tuple[str, int]] = []
        for item in raw:
            pairs.extend(_label_pairs(item))
        return pairs
    if not isinstance(raw, dict):
        return []
    code = ""
    for key in _CODE_KEYS:
        value = raw.get(key)
        text = str(value).strip() if value is not None else ""
        if text:
            code = text
            break
    if code:
        return [(code, _count_or_one(raw))]
    pairs = []
    for key, value in raw.items():
        name = str(key).strip()
        if not name:
            continue
        try:
            count = int(value)
        except (TypeError, ValueError):
            continue
        pairs.append((name, count))
    return pairs


def _risk_windows(day: str, raw: Any) -> tuple[RiskWindow, ...]:
    if not isinstance(raw, list):
        return ()
    windows: list[RiskWindow] = []
    for stmt in raw:
        if not isinstance(stmt, dict):
            continue
        doc = stmt.get("riskEventDoc")
        text = str(doc).strip() if doc else ""
        start = str(stmt.get("startHour") or "").strip()
        end = str(stmt.get("endHour") or "").strip()
        count = _int_field(stmt, "count")
        if not text and not start and not end and count == 0:
            continue
        windows.append(
            RiskWindow(
                date=day,
                start_hour=start,
                end_hour=end,
                count=count,
                text=text,
            )
        )
    return tuple(windows)


def _timings(raw: Any) -> tuple[LabelTiming, ...]:
    if not isinstance(raw, list):
        return ()
    rows: list[LabelTiming] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        label = str(item.get("labelType") or "").strip()
        if not label:
            continue
        times_raw = item.get("alarmDateTimeArr")
        times = (
            tuple(str(value).strip() for value in times_raw if str(value).strip())
            if isinstance(times_raw, list)
            else ()
        )
        buckets_raw = item.get("timeDistribute")
        buckets: list[int] = []
        if isinstance(buckets_raw, list):
            for value in buckets_raw:
                try:
                    buckets.append(int(value))
                except (TypeError, ValueError):
                    buckets.append(0)
        rows.append(LabelTiming(label=label, times=times, buckets=tuple(buckets)))
    return tuple(rows)


def parse_alarm_message_statistics(data: Any) -> InsightBriefing:
    """Parse getAlarmMessageStatistics data."""
    if not isinstance(data, dict):
        return InsightBriefing(daily=(), risk_notes=())

    by_date: dict[str, dict[str, Any]] = {}

    def slot(date: str) -> dict[str, Any]:
        return by_date.setdefault(
            date,
            {
                "total": 0,
                "human": 0,
                "vehicle": 0,
                "pet": 0,
                "package": 0,
                "events": [],
                "risks": [],
                "timings": [],
            },
        )

    stats = data.get("statistics")
    if isinstance(stats, list):
        for row in stats:
            if not isinstance(row, dict):
                continue
            date_raw = row.get("date")
            date = str(date_raw).strip() if date_raw else ""
            if not date:
                continue
            current = slot(date)
            current["total"] = _int_field(row, "totalCount", "totalcount")
            current["human"] = _int_field(row, "humanAlarm")
            current["vehicle"] = _int_field(row, "carAlarm")
            current["pet"] = _int_field(row, "petAlarm")
            current["package"] = _int_field(row, "packageAlarm")
            current["events"] = [
                IdentifiedEvent(code, count)
                for code, count in _label_pairs(row.get("bigModelStatisticsLabels"))
            ]

    ai_rows = data.get("aiStatisticsAnalysisResult")
    if isinstance(ai_rows, list):
        for day in ai_rows:
            if not isinstance(day, dict):
                continue
            analysis_day = day.get("analysisDay")
            date = str(analysis_day).strip() if analysis_day else ""
            if not date:
                continue
            current = slot(date)
            current["risks"] = list(_risk_windows(date, day.get("riskStatementInfo")))
            current["timings"] = list(_timings(day.get("msgAnalysisInfo")))

    daily_rows: list[DailyAlarmRollup] = []
    notes: list[str] = []
    for date, current in by_date.items():
        risks = tuple(current["risks"])
        daily_rows.append(
            DailyAlarmRollup(
                date=date,
                total=current["total"],
                human=current["human"],
                vehicle=current["vehicle"],
                pet=current["pet"],
                package=current["package"],
                events=tuple(current["events"]),
                risks=risks,
                timings=tuple(current["timings"]),
            )
        )
        for risk in risks:
            if not risk.text:
                continue
            window = ""
            if risk.start_hour and risk.end_hour:
                window = f" ({risk.start_hour}:00-{risk.end_hour}:00)"
            notes.append(f"{date}: {risk.text}{window}")

    return InsightBriefing(daily=tuple(daily_rows), risk_notes=tuple(notes))


def format_briefing_markdown(briefing: InsightBriefing) -> str:
    """Turn parsed briefing into Markdown for a Lovelace card."""
    if not briefing.daily and not briefing.risk_notes:
        return "No briefing data for this period."

    lines: list[str] = []
    sentences = [risk.text for row in briefing.daily for risk in row.risks if risk.text]
    lines.append(sentences[0] if sentences else "Nothing unusual today.")
    for row in briefing.daily:
        totals = detection_totals(row.events)
        lines.append(
            "Detections: "
            + ", ".join(f"{key} {totals[key]}" for key in _DETECTION_KEYS)
        )
        if row.events:
            lines.append("Identified events:")
            lines.extend(f"- {event.code} {event.count}" for event in row.events)
        periods = [
            f"{risk.start_hour}:00-{risk.end_hour}:00"
            for risk in row.risks
            if risk.start_hour and risk.end_hour and risk.count
        ]
        risk_count = sum(risk.count for risk in row.risks)
        lines.append("Risk periods: " + (", ".join(periods) if periods else "-"))
        lines.append(f"Risk count: {risk_count}")
    lines.append("")
    lines.append("### Daily totals")
    if briefing.daily:
        for row in briefing.daily:
            parts = [
                f"**{row.date}** — {row.total} alarms",
                f"person {row.human}",
                f"vehicle {row.vehicle}",
                f"pet {row.pet}",
                f"package {row.package}",
            ]
            lines.append("- " + ", ".join(parts))
    else:
        lines.append("- No daily rollups returned.")

    if briefing.risk_notes:
        lines.append("")
        lines.append("### Risk highlights")
        for note in briefing.risk_notes[:20]:
            lines.append(f"- {note}")

    return "\n".join(lines)
