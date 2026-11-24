"""AI Insight (智见) Open API helpers."""

from .cloud import (
    DeviceCloudService,
    ai_insight_cloud_label_from_service,
    ai_insight_label_from_status,
    ai_insight_label_from_strategy_status,
    parse_ai_insight_strategy_status,
    parse_device_cloud_data,
)
from .search import (
    InsightAlarmHit,
    format_search_results_markdown,
    parse_search_ai_alarms,
)
from .statistics import (
    InsightBriefing,
    format_briefing_markdown,
    parse_alarm_message_statistics,
)

__all__ = [
    "DeviceCloudService",
    "InsightAlarmHit",
    "InsightBriefing",
    "ai_insight_cloud_label_from_service",
    "ai_insight_label_from_status",
    "ai_insight_label_from_strategy_status",
    "format_briefing_markdown",
    "format_search_results_markdown",
    "parse_ai_insight_strategy_status",
    "parse_alarm_message_statistics",
    "parse_device_cloud_data",
    "parse_search_ai_alarms",
]
