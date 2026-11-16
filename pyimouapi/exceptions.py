from __future__ import annotations

import sys
import traceback


class ImouException(Exception):
    def __init__(
        self,
        message: str = "",
        *,
        status_code: int | None = None,
        api_code: str | None = None,
    ) -> None:
        """Initialize."""
        self.message = message
        self.status_code = status_code
        self.api_code = api_code
        super().__init__(self.message)

    def to_string(self) -> str:
        """Return the exception as a string."""
        return f"{self.__class__.__name__}: {self.message}\n" + self.traceback()

    def traceback(self) -> str:
        """Return the traceback as a string."""
        exc_info = sys.exc_info()
        if exc_info[0] is None:
            return ""
        return "".join(traceback.format_exception(*exc_info))

    def get_title(self) -> str:
        """Return the title of the exception which will be then translated."""
        return "generic_error"


class ConnectFailedException(ImouException):
    """connectFailedException."""

    def get_title(self) -> str:
        """Return the title of the exception which will be then translated."""
        return "connect_failed"


class RequestFailedException(ImouException):
    """requestFailedException"""

    def get_title(self) -> str:
        """Return the title of the exception which will be then translated."""
        return "request_failed"


class InvalidAppIdOrSecretException(ImouException):
    """invalidAppIdOrSecretException"""

    def get_title(self) -> str:
        """Return the title of the exception which will be then translated."""
        return "appIdOrSecret_invalid"
