"""Fixed-safe failure vocabulary for the PMQA local API boundary."""

from enum import Enum


class WebAPIFailureCode(str, Enum):
    INVALID_REQUEST = "invalid_request"
    AUTHENTICATION_FAILED = "authentication_failed"
    HOST_FAILED = "host_failed"
    ORIGIN_FAILED = "origin_failed"
    CSRF_FAILED = "csrf_failed"
    REQUEST_TOO_LARGE = "request_too_large"
    RESOURCE_NOT_FOUND = "resource_not_found"
    CONVERSATION_FAILED = "conversation_failed"
    INTERNAL_FAILED = "internal_failed"


_FAILURE_MESSAGES = {
    WebAPIFailureCode.INVALID_REQUEST: "invalid PMQA API request",
    WebAPIFailureCode.AUTHENTICATION_FAILED:
        "PMQA API authentication failed",
    WebAPIFailureCode.HOST_FAILED: "PMQA API Host validation failed",
    WebAPIFailureCode.ORIGIN_FAILED: "PMQA API Origin validation failed",
    WebAPIFailureCode.CSRF_FAILED: "PMQA API CSRF validation failed",
    WebAPIFailureCode.REQUEST_TOO_LARGE: "PMQA API request is too large",
    WebAPIFailureCode.RESOURCE_NOT_FOUND:
        "PMQA API resource was not found",
    WebAPIFailureCode.CONVERSATION_FAILED:
        "PMQA conversation operation failed",
    WebAPIFailureCode.INTERNAL_FAILED: "PMQA API internal operation failed",
}


class WebAPIError(RuntimeError):
    """Carry only one stable code, status, and fixed-safe message."""

    def __init__(self, code: WebAPIFailureCode, status_code: int) -> None:
        if (
            type(code) is not WebAPIFailureCode
            or type(status_code) is not int
            or status_code < 400
            or status_code > 599
        ):
            raise TypeError("invalid Web API error")
        self.code = code
        self.status_code = status_code
        super().__init__(_FAILURE_MESSAGES[code])


def web_error_message(code: WebAPIFailureCode) -> str:
    if type(code) is not WebAPIFailureCode:
        raise TypeError("code must be a WebAPIFailureCode")
    return _FAILURE_MESSAGES[code]


__all__ = [
    "WebAPIError",
    "WebAPIFailureCode",
    "web_error_message",
]
