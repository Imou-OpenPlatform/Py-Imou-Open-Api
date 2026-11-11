"""searchAiAlarmMessageByPage parsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class InsightAlarmHit:
    """One AI search result row."""

    alarm_id: str | None
    begin_time: str | None
    ai_copywriting: str | None
    security_risk_level: int | None
    ai_tags: tuple[str, ...]
    thumb_url: str | None


def parse_search_ai_alarms(data: Any) -> tuple[str | None, list[InsightAlarmHit]]:
    """Parse search API data; returns (nextIndexId, alarms)."""
    if not isinstance(data, dict):
        return None, []
    next_index = data.get("nextIndexId")
    next_id = str(next_index).strip() if next_index not in (None, "") else None
    alarms_raw = data.get("alarms")
    if not isinstance(alarms_raw, list):
        return next_id, []
    hits: list[InsightAlarmHit] = []
    for row in alarms_raw:
        if not isinstance(row, dict):
            continue
        alarm_id = row.get("alarmId")
        aid = str(alarm_id).strip() if alarm_id else None
        local_date = row.get("localDate")
        begin = str(local_date).strip() if local_date else None
        copy_raw = row.get("aiCopyWriting")
        copywriting = str(copy_raw).strip() if copy_raw else None
        risk_raw = row.get("securityRiskLevel")
        risk = None
        if risk_raw is not None:
            try:
                risk = int(risk_raw)
            except (TypeError, ValueError):
                risk = None
        tags_raw = row.get("aiTag")
        tags: list[str] = []
        if isinstance(tags_raw, list):
            tags = [str(item).strip() for item in tags_raw if str(item).strip()]
        thumb = row.get("thumbUrl")
        thumb_url = str(thumb).strip() if thumb else None
        hits.append(
            InsightAlarmHit(
                alarm_id=aid,
                begin_time=begin,
                ai_copywriting=copywriting,
                security_risk_level=risk,
                ai_tags=tuple(tags),
                thumb_url=thumb_url,
            )
        )
    return next_id, hits


def format_search_results_markdown(hits: list[InsightAlarmHit], *, keyword: str) -> str:
    """Format search hits as Markdown."""
    if not hits:
        return f'No alarms matched "{keyword}".'
    lines = [f'### Matches for "{keyword}"', ""]
    for hit in hits[:32]:
        time_label = hit.begin_time or "—"
        copy = hit.ai_copywriting or "(no description)"
        tags = ", ".join(hit.ai_tags) if hit.ai_tags else ""
        risk = ""
        if hit.security_risk_level is not None:
            risk = f" (risk {hit.security_risk_level})"
        line = f"- **{time_label}** — {copy}{risk}"
        if tags:
            line = f"{line} — {tags}"
        lines.append(line)
    if len(hits) > 32:
        lines.append("")
        lines.append(f"_Showing 32 of {len(hits)} results._")
    return "\n".join(lines)
