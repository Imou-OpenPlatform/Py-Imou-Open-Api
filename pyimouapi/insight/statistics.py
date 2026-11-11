"""getAlarmMessageStatistics parsing and briefing text."""

from __future__ import annotations

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


@dataclass(frozen=True, slots=True)
class DailyAlarmRollup:
    """One row from the statistics array."""

    date: str
    total: int
    human: int
    vehicle: int
    pet: int
    motion: int


@dataclass(frozen=True, slots=True)
class InsightBriefing:
    """Parsed statistics API payload."""

    daily: tuple[DailyAlarmRollup, ...]
    risk_notes: tuple[str, ...]


def _int_field(row: dict[str, Any], key: str) -> int:
    raw = row.get(key)
    if raw is None:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def parse_alarm_message_statistics(data: Any) -> InsightBriefing:
    """Parse getAlarmMessageStatistics data."""
    if not isinstance(data, dict):
        return InsightBriefing(daily=(), risk_notes=())

    daily_rows: list[DailyAlarmRollup] = []
    stats = data.get("statistics")
    if isinstance(stats, list):
        for row in stats:
            if not isinstance(row, dict):
                continue
            date_raw = row.get("date")
            date = str(date_raw).strip() if date_raw else ""
            if not date:
                continue
            daily_rows.append(
                DailyAlarmRollup(
                    date=date,
                    total=_int_field(row, "totalcount"),
                    human=_int_field(row, "humanAlarm"),
                    vehicle=_int_field(row, "carAlarm"),
                    pet=_int_field(row, "petAlarm"),
                    motion=_int_field(row, "motionAlarm"),
                )
            )

    risks: list[str] = []
    ai_rows = data.get("aiStatisticsAnalysisResult")
    if isinstance(ai_rows, list):
        for day in ai_rows:
            if not isinstance(day, dict):
                continue
            analysis_day = day.get("analysisDay")
            day_label = str(analysis_day).strip() if analysis_day else ""
            statements = day.get("riskStatementInfo")
            if not isinstance(statements, list):
                continue
            for stmt in statements:
                if not isinstance(stmt, dict):
                    continue
                doc = stmt.get("riskEventDoc")
                text = str(doc).strip() if doc else ""
                if not text:
                    continue
                start = stmt.get("startHour")
                end = stmt.get("endHour")
                window = ""
                if start not in (None, "") and end not in (None, ""):
                    window = f" ({start}:00-{end}:00)"
                prefix = f"{day_label}: " if day_label else ""
                risks.append(f"{prefix}{text}{window}")

    return InsightBriefing(daily=tuple(daily_rows), risk_notes=tuple(risks))


def format_briefing_markdown(briefing: InsightBriefing) -> str:
    """Turn parsed briefing into Markdown for a Lovelace card."""
    if not briefing.daily and not briefing.risk_notes:
        return "No briefing data for this period."

    lines: list[str] = ["### Daily totals"]
    if briefing.daily:
        for row in briefing.daily:
            parts = [
                f"**{row.date}** — {row.total} alarms",
                f"person {row.human}",
                f"vehicle {row.vehicle}",
                f"pet {row.pet}",
                f"motion {row.motion}",
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
