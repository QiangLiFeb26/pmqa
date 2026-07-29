"""Exact packaged-resource allowlist for the local PMQA workbench."""

from __future__ import annotations

import hashlib
import hmac
import json
from importlib.resources import files
from types import MappingProxyType
from typing import Mapping, Tuple


STATIC_ROUTE_CONTENT_TYPES = MappingProxyType(
    {
        "/": "text/html; charset=utf-8",
        "/assets/app.js": "text/javascript; charset=utf-8",
        "/assets/app.css": "text/css; charset=utf-8",
    }
)
STATIC_ROUTE_FILENAMES = MappingProxyType(
    {
        "/": "index.html",
        "/assets/app.js": "assets/app.js",
        "/assets/app.css": "assets/app.css",
    }
)
STATIC_ROUTES = frozenset(STATIC_ROUTE_FILENAMES)


class PMQAWebStaticAssetError(RuntimeError):
    """Report one fixed packaged-asset configuration failure."""

    def __init__(self) -> None:
        super().__init__("invalid PMQA Web packaged assets")


def load_packaged_web_assets() -> Mapping[str, Tuple[bytes, str]]:
    """Load only the exact immutable workbench assets from this distribution."""

    selected = {}
    try:
        root = files("pmqa.web").joinpath("static")
        integrity = json.loads(
            root.joinpath("asset-integrity.json").read_text(encoding="utf-8")
        )
        expected_files = set(STATIC_ROUTE_FILENAMES.values())
        if (
            type(integrity) is not dict
            or set(integrity) != {"schema_version", "files"}
            or integrity.get("schema_version") != "1"
            or type(integrity.get("files")) is not dict
            or set(integrity["files"]) != expected_files
        ):
            raise PMQAWebStaticAssetError()
        for route, filename in STATIC_ROUTE_FILENAMES.items():
            content = root.joinpath(*filename.split("/")).read_bytes()
            expected_digest = integrity["files"].get(filename)
            actual_digest = hashlib.sha256(content).hexdigest()
            if (
                not content
                or type(expected_digest) is not str
                or len(expected_digest) != 64
                or not hmac.compare_digest(expected_digest, actual_digest)
            ):
                raise PMQAWebStaticAssetError()
            selected[route] = (
                content,
                STATIC_ROUTE_CONTENT_TYPES[route],
            )
    except PMQAWebStaticAssetError:
        raise
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        OSError,
        TypeError,
        ValueError,
    ):
        raise PMQAWebStaticAssetError() from None
    return MappingProxyType(selected)


__all__ = [
    "PMQAWebStaticAssetError",
    "STATIC_ROUTES",
    "load_packaged_web_assets",
]
