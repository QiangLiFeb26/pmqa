"""Runtime-only security configuration for the loopback PMQA Web boundary."""

from __future__ import annotations

import hmac
import re
from typing import Any


_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43,128}$", flags=re.ASCII)
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1"})


class PMQAWebSecurityConfigurationError(ValueError):
    """Report one fixed safe local Web security configuration failure."""

    def __init__(self) -> None:
        super().__init__("invalid PMQA Web security configuration")


class PMQAWebSecurityContext:
    """Hold invocation-local tokens without exposing or serializing them."""

    __slots__ = (
        "__csrf_token",
        "__host",
        "__host_authority",
        "__origin",
        "__port",
        "__session_token",
    )

    def __init__(
        self,
        *,
        session_token: str,
        csrf_token: str,
        host: str,
        port: int,
    ) -> None:
        if (
            type(session_token) is not str
            or type(csrf_token) is not str
            or _TOKEN_PATTERN.fullmatch(session_token) is None
            or _TOKEN_PATTERN.fullmatch(csrf_token) is None
            or hmac.compare_digest(session_token, csrf_token)
            or type(host) is not str
            or host not in _LOOPBACK_HOSTS
            or type(port) is not int
            or port < 1
            or port > 65535
        ):
            raise PMQAWebSecurityConfigurationError() from None

        authority_host = f"[{host}]" if host == "::1" else host
        self.__session_token = session_token
        self.__csrf_token = csrf_token
        self.__host = host
        self.__port = port
        self.__host_authority = f"{authority_host}:{port}"
        self.__origin = f"http://{self.__host_authority}"

    @property
    def host(self) -> str:
        return self.__host

    @property
    def port(self) -> int:
        return self.__port

    @property
    def host_authority(self) -> str:
        return self.__host_authority

    @property
    def origin(self) -> str:
        return self.__origin

    def authenticates(self, candidate: Any) -> bool:
        return type(candidate) is str and hmac.compare_digest(
            candidate,
            self.__session_token,
        )

    def validates_csrf(self, candidate: Any) -> bool:
        return type(candidate) is str and hmac.compare_digest(
            candidate,
            self.__csrf_token,
        )

    def contains_runtime_token(self, candidate: Any) -> bool:
        if type(candidate) is not str or len(candidate) > 64 * 1024:
            return False
        return (
            self.__session_token in candidate
            or self.__csrf_token in candidate
        )

    def __repr__(self) -> str:
        return "PMQAWebSecurityContext(<redacted>)"

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        _ = memo
        return self

    def __reduce_ex__(self, protocol):
        _ = protocol
        raise TypeError("PMQA Web security context is runtime-only")


__all__ = [
    "PMQAWebSecurityConfigurationError",
    "PMQAWebSecurityContext",
]
