"""Retry user-initiated writes once when a sleep-capable device is dormant."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from .const import (
    ERROR_CODE_DEVICE_OFFLINE,
    ERROR_CODE_DEVICE_SLEEPING,
    PARAM_BATTERY,
    PARAM_STATE,
    PARAM_STATUS,
)
from .exceptions import InvalidAppIdOrSecretException, RequestFailedException

_LOGGER = logging.getLogger(__name__)

DEVICE_STATUS_SLEEP = "sleep"

# Seconds to wait before retrying a control write on a sleeping device.
DORMANT_WRITE_RETRY_WAIT_SECONDS = 10

# Platform codes seen when a dormant device cannot accept a write yet.
DORMANT_WRITE_RETRY_ERROR_CODES = frozenset(
    {
        ERROR_CODE_DEVICE_SLEEPING,
        ERROR_CODE_DEVICE_OFFLINE,
        "DV1026",
    }
)


def device_is_sleeping(device: Any) -> bool:
    """Return True when the status sensor reports sleep."""
    status = device.sensors.get(PARAM_STATUS, {}).get(PARAM_STATE)
    return status == DEVICE_STATUS_SLEEP


def device_supports_dormant_retry(device: Any) -> bool:
    """Return True for battery / dormant-capable devices (not mains-only)."""
    if PARAM_BATTERY in device.sensors:
        return True
    for ability in (device.device_ability, device.channel_ability):
        if isinstance(ability, str) and "Dormant" in ability:
            return True
    return False


def is_dormant_retryable_error(exc: BaseException) -> bool:
    """Return True when the platform error may clear after a short wait."""
    if not isinstance(exc, RequestFailedException):
        return False
    message = exc.message
    return any(code in message for code in DORMANT_WRITE_RETRY_ERROR_CODES)


async def async_dormant_write_retry(
    device: Any,
    operation: Callable[[], Awaitable[None]],
) -> None:
    """Run a control write; on asleep-device failure, wait and retry once."""
    try:
        await operation()
    except InvalidAppIdOrSecretException:
        raise
    except RequestFailedException as first:
        if not (
            device_is_sleeping(device)
            and device_supports_dormant_retry(device)
            and is_dormant_retryable_error(first)
        ):
            raise
        _LOGGER.debug(
            "Control write for %s failed while asleep (%s); retrying after %ss",
            device.device_name,
            first.message,
            DORMANT_WRITE_RETRY_WAIT_SECONDS,
        )
        await asyncio.sleep(DORMANT_WRITE_RETRY_WAIT_SECONDS)
        await operation()
