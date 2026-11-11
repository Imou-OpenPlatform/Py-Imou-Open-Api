"""Build ``inputData`` for common v2 service buttons."""

from __future__ import annotations

from typing import Any

from ..const import BUTTON_TYPE_PARAM_VALUE, V2_PTZ_STEP_OPERATOR


def v2_service_input_data(
    service_id: str,
    button_type: str,
    duration: int,
) -> dict[str, Any]:
    """Map legacy button keys to v2 ``device.service.invoke`` inputData."""
    if service_id == "ptz.aim.step":
        operator = V2_PTZ_STEP_OPERATOR.get(button_type)
        if operator is None:
            return {}
        return {"operator": operator, "zoom": "1"}
    if service_id == "ptz.aim.relative":
        operation = BUTTON_TYPE_PARAM_VALUE.get(button_type)
        if operation is None:
            return {}
        horizontal, vertical = "0", "0"
        if operation == 0:
            vertical = "0.5"
        elif operation == 1:
            vertical = "-0.5"
        elif operation == 2:
            horizontal = "-0.5"
        elif operation == 3:
            horizontal = "0.5"
        return {
            "horizontal": horizontal,
            "vertical": vertical,
            "zoom": "0",
            "duration": duration,
        }
    return {}
