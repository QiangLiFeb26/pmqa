"""Deterministic scaffolding and offline source conformance for Product Packs."""

from dataclasses import dataclass
from enum import Enum
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
from typing import Dict, Optional, Tuple

from pmqa.product_pack.manifest import (
    ProductPackManifest,
)


PRODUCT_PACK_SCAFFOLD_VERSION = "1"
_MAX_PATH_LENGTH = 4096
_MAX_CONTROL_FILE_BYTES = 256 * 1024
_SEPARATOR_PATTERN = re.compile(r"[._-]+", flags=re.ASCII)
_DISTRIBUTION_IDENTITY_PATTERN = re.compile(
    r"^pmqa-product-pack-[a-z0-9]+(?:-[a-z0-9]+)*$",
    flags=re.ASCII,
)
_PYTHON_PACKAGE_IDENTITY_PATTERN = re.compile(
    r"^pmqa_product_pack_[a-z0-9]+(?:_[a-z0-9]+)*$",
    flags=re.ASCII,
)
_STATIC_GENERATED_FILES = (
    ".gitignore",
    "README.md",
    "bridge/package.json",
    "bridge/src/capture_backend.ts",
    "bridge/src/main.ts",
    "bridge/src/protocol.ts",
    "bridge/tsconfig.json",
    "product-pack.json",
    "pyproject.toml",
    "tests/test_manifest.py",
)


class ProductPackScaffoldErrorCode(str, Enum):
    """Stable failures for scaffold requests and publication."""

    INVALID_REQUEST = "invalid_request"
    UNSAFE_OUTPUT_PATH = "unsafe_output_path"
    TARGET_EXISTS = "target_exists"
    GENERATION_FAILED = "generation_failed"


_SCAFFOLD_ERROR_MESSAGES = {
    ProductPackScaffoldErrorCode.INVALID_REQUEST: (
        "invalid Product Pack scaffold request"
    ),
    ProductPackScaffoldErrorCode.UNSAFE_OUTPUT_PATH: (
        "Product Pack scaffold output path is unsafe"
    ),
    ProductPackScaffoldErrorCode.TARGET_EXISTS: (
        "Product Pack scaffold target already exists"
    ),
    ProductPackScaffoldErrorCode.GENERATION_FAILED: (
        "Product Pack scaffold generation failed"
    ),
}


class ProductPackScaffoldError(ValueError):
    """Expose only a fixed scaffold failure code and safe message."""

    def __init__(self, code: ProductPackScaffoldErrorCode) -> None:
        self.code = code
        super().__init__(_SCAFFOLD_ERROR_MESSAGES[code])


class ProductPackSourceConformanceErrorCode(str, Enum):
    """Stable, bounded reasons a source tree can fail conformance."""

    INVALID_REQUEST = "invalid_request"
    INVALID_LAYOUT = "invalid_layout"
    INVALID_MANIFEST = "invalid_manifest"
    MANIFEST_MISMATCH = "manifest_mismatch"
    INVALID_PYTHON_DISTRIBUTION = "invalid_python_distribution"
    INVALID_BRIDGE_SOURCE = "invalid_bridge_source"


_CONFORMANCE_MESSAGES = {
    ProductPackSourceConformanceErrorCode.INVALID_REQUEST: (
        "invalid Product Pack source validation request"
    ),
    ProductPackSourceConformanceErrorCode.INVALID_LAYOUT: (
        "Product Pack source layout is invalid"
    ),
    ProductPackSourceConformanceErrorCode.INVALID_MANIFEST: (
        "Product Pack source manifest is invalid"
    ),
    ProductPackSourceConformanceErrorCode.MANIFEST_MISMATCH: (
        "Product Pack source manifest does not match"
    ),
    ProductPackSourceConformanceErrorCode.INVALID_PYTHON_DISTRIBUTION: (
        "Product Pack Python distribution is invalid"
    ),
    ProductPackSourceConformanceErrorCode.INVALID_BRIDGE_SOURCE: (
        "Product Pack bridge source is invalid"
    ),
}


@dataclass(frozen=True)
class ProductPackScaffoldRequest:
    """One validated manifest and one explicit absolute output directory."""

    manifest: ProductPackManifest
    output_directory: str

    def __post_init__(self) -> None:
        if (
            type(self.manifest) is not ProductPackManifest
            or not _is_canonical_absolute_path(self.output_directory)
        ):
            _raise_scaffold_error(ProductPackScaffoldErrorCode.INVALID_REQUEST)


@dataclass(frozen=True)
class ProductPackScaffoldResult:
    """Immutable, path-free summary of a generated source scaffold."""

    scaffold_version: str
    distribution_name: str
    python_package_name: str
    generated_files: Tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            self.scaffold_version != PRODUCT_PACK_SCAFFOLD_VERSION
            or type(self.distribution_name) is not str
            or _DISTRIBUTION_IDENTITY_PATTERN.fullmatch(
                self.distribution_name
            ) is None
            or type(self.python_package_name) is not str
            or _PYTHON_PACKAGE_IDENTITY_PATTERN.fullmatch(
                self.python_package_name
            ) is None
            or self.distribution_name.removeprefix(
                "pmqa-product-pack-"
            ).replace("-", "_")
            != self.python_package_name.removeprefix("pmqa_product_pack_")
            or not _are_valid_generated_files(self.generated_files)
        ):
            _raise_scaffold_error(ProductPackScaffoldErrorCode.INVALID_REQUEST)


@dataclass(frozen=True)
class ProductPackSourceConformanceResult:
    """Immutable result containing no source content or filesystem paths."""

    is_conformant: bool
    error_code: Optional[ProductPackSourceConformanceErrorCode]

    def __post_init__(self) -> None:
        if type(self.is_conformant) is not bool or (
            self.is_conformant != (self.error_code is None)
        ):
            raise ValueError("invalid Product Pack conformance result")
        if self.error_code is not None and type(self.error_code) is not (
            ProductPackSourceConformanceErrorCode
        ):
            raise ValueError("invalid Product Pack conformance result")

    @property
    def message(self) -> str:
        """Return one fixed safe status message."""

        if self.error_code is None:
            return "Product Pack source conforms"
        return _CONFORMANCE_MESSAGES[self.error_code]


@dataclass(frozen=True)
class _DerivedIdentity:
    distribution_name: str
    python_package_name: str


def _are_valid_generated_files(value: object) -> bool:
    if type(value) is not tuple or len(value) != 12:
        return False
    if value != tuple(sorted(value)) or any(type(item) is not str for item in value):
        return False
    static = set(_STATIC_GENERATED_FILES)
    dynamic = [item for item in value if item not in static]
    return (
        len(dynamic) == 2
        and dynamic[0].startswith("src/pmqa_product_pack_")
        and dynamic[0].endswith("/__init__.py")
        and dynamic[1].startswith("src/pmqa_product_pack_")
        and dynamic[1].endswith("/manifest.py")
        and dynamic[0].rsplit("/", 1)[0] == dynamic[1].rsplit("/", 1)[0]
    )


def _derive_identity(manifest: ProductPackManifest) -> _DerivedIdentity:
    normalized = _SEPARATOR_PATTERN.sub("_", manifest.pack_id)
    distribution_suffix = _SEPARATOR_PATTERN.sub("-", manifest.pack_id)
    return _DerivedIdentity(
        distribution_name="pmqa-product-pack-" + distribution_suffix,
        python_package_name="pmqa_product_pack_" + normalized,
    )


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ) + "\n"


def _manifest_module(manifest: ProductPackManifest) -> str:
    payload = json.dumps(
        manifest.to_dict(),
        ensure_ascii=False,
        allow_nan=False,
        indent=4,
    )
    return (
        '"""Declarative Product Pack manifest entry point."""\n\n'
        "def product_pack_manifest():\n"
        "    return "
        + payload.replace("\n", "\n    ")
        + "\n\n\n"
        "PRODUCT_PACK_MANIFEST = product_pack_manifest()"
        "\n"
    )


def _pyproject(manifest: ProductPackManifest, identity: _DerivedIdentity) -> str:
    return f'''[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "{identity.distribution_name}"
version = "{manifest.pack_version}"
description = "External PMQA Product Pack manifest"
requires-python = ">=3.9"

[project.entry-points."pmqa.product_packs"]
"{manifest.pack_id}" = "{identity.python_package_name}.manifest:PRODUCT_PACK_MANIFEST"

[tool.setuptools.packages.find]
where = ["src"]
include = ["{identity.python_package_name}"]
namespaces = false
'''


def _package_json(manifest: ProductPackManifest) -> str:
    identity = _derive_identity(manifest)
    value = {
        "name": identity.distribution_name + "-bridge",
        "version": manifest.pack_version,
        "private": True,
        "type": "module",
        "engines": {"node": ">=20"},
        "scripts": {"build": "tsc -p tsconfig.json"},
    }
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def _tsconfig() -> str:
    return '''{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "rootDir": "src",
    "outDir": "dist",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true
  },
  "include": ["src/**/*.ts"]
}
'''


def _protocol_ts() -> str:
    return '''export const BRIDGE_PROTOCOL_VERSION = "1" as const;

export type BridgeOperation = "exploration_capture";
export type BridgeStatus = "succeeded" | "failed";
export type BridgeFailureCode =
  | "exploration_failed"
  | "action_plan_rejected"
  | "protocol_failure";

export interface BridgeRequestV1 {
  protocol_version: "1";
  request_id: string;
  workflow_id: string;
  product_id: string;
  pack_id: string;
  tool_id: string;
  operation: "exploration_capture";
  requested_at: string;
  action_plan: string[];
}

export interface ExplorationSourceV1 {
  source_type: string;
  tool_id: string;
  capture_id: string;
}

export interface ObservedPageV1 {
  page_id: string;
  url: string;
  title: string;
  structural_fingerprint: string;
}

export interface ObservedAttributeV1 {
  name: string;
  value: string;
}

export interface ObservedElementV1 {
  element_id: string;
  page_id: string;
  role: string;
  accessible_name: string;
  visible_text: string | null;
  attributes: ObservedAttributeV1[];
}

export interface LocatorCandidateObservationV1 {
  locator_candidate_id: string;
  element_id: string;
  strategy: string;
  value: string;
  priority: number;
}

export interface InteractionObservationV1 {
  interaction_id: string;
  source_page_id: string;
  target_element_id: string;
  action: string;
  outcome_type: string;
  outcome_value: string;
}

export interface ExplorationEvidenceV1 {
  schema_version: string;
  evidence_id: string;
  workflow_id: string;
  product_id: string;
  source: ExplorationSourceV1;
  captured_at: string;
  pages: ObservedPageV1[];
  elements: ObservedElementV1[];
  locator_candidates: LocatorCandidateObservationV1[];
  interactions: InteractionObservationV1[];
}

export interface BridgeResponseV1 {
  protocol_version: "1";
  request_id: string;
  workflow_id: string;
  product_id: string;
  pack_id: string;
  tool_id: string;
  operation: "exploration_capture";
  status: BridgeStatus;
  completed_at: string;
  evidence: ExplorationEvidenceV1 | null;
  failure_code: BridgeFailureCode | null;
}
'''


def _capture_backend_ts() -> str:
    return '''import type { BridgeRequestV1, BridgeResponseV1 } from "./protocol.js";

export interface ProductCaptureBackend {
  capture(request: BridgeRequestV1): Promise<BridgeResponseV1>;
}

export class UnimplementedCaptureBackend implements ProductCaptureBackend {
  async capture(request: BridgeRequestV1): Promise<BridgeResponseV1> {
    return {
      protocol_version: "1",
      request_id: request.request_id,
      workflow_id: request.workflow_id,
      product_id: request.product_id,
      pack_id: request.pack_id,
      tool_id: request.tool_id,
      operation: request.operation,
      status: "failed",
      completed_at: request.requested_at,
      evidence: null,
      failure_code: "protocol_failure",
    };
  }
}
'''


def _main_ts() -> str:
    return '''import { UnimplementedCaptureBackend } from "./capture_backend.js";
import type { BridgeRequestV1 } from "./protocol.js";

async function readRequest(): Promise<BridgeRequestV1> {
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) {
    chunks.push(Buffer.from(chunk));
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8")) as BridgeRequestV1;
}

async function main(): Promise<void> {
  const request = await readRequest();
  const response = await new UnimplementedCaptureBackend().capture(request);
  process.stdout.write(JSON.stringify(response));
}

main().catch(() => {
  process.stderr.write("Product Pack bridge failed\\n");
  process.exitCode = 1;
});
'''


def _readme() -> str:
    return '''# External PMQA Product Pack

This experimental scaffold is non-operational and fails closed until the
consumer implements `ProductCaptureBackend` with an explicitly approved direct
Playwright TypeScript integration. Choose and pin the Playwright version under
the consumer team's dependency policy; this scaffold performs no installation.

Build the Python manifest distribution with the approved offline build tooling.
Build the bridge explicitly after adding consumer-owned implementation and
dependencies. Standard PMQA integration uses Bridge Protocol v1 over bounded
stdin/stdout transport. No IDE-specific integration is required. Keep
credentials in the consumer execution environment and never in the manifest
or generated source.
'''


def _gitignore() -> str:
    return '''.env
.env.*
*.pyc
*.sqlite
*.sqlite3
__pycache__/
.pytest_cache/
*.egg-info/
build/
dist/
node_modules/
bridge/dist/
artifacts/
screenshots/
test-results/
traces/
'''


def _manifest_test(identity: _DerivedIdentity) -> str:
    return f'''from {identity.python_package_name}.manifest import PRODUCT_PACK_MANIFEST


def test_manifest_entry_point_is_plain_dictionary():
    assert type(PRODUCT_PACK_MANIFEST) is dict
    assert PRODUCT_PACK_MANIFEST["schema_version"] == "1"
    assert PRODUCT_PACK_MANIFEST["product_pack_api_version"] == "1"
'''


def _render_files(manifest: ProductPackManifest) -> Dict[str, str]:
    identity = _derive_identity(manifest)
    package = identity.python_package_name
    return {
        ".gitignore": _gitignore(),
        "README.md": _readme(),
        "bridge/package.json": _package_json(manifest),
        "bridge/src/capture_backend.ts": _capture_backend_ts(),
        "bridge/src/main.ts": _main_ts(),
        "bridge/src/protocol.ts": _protocol_ts(),
        "bridge/tsconfig.json": _tsconfig(),
        "product-pack.json": _canonical_json(manifest.to_dict()),
        "pyproject.toml": _pyproject(manifest, identity),
        "src/{}/__init__.py".format(package): "",
        "src/{}/manifest.py".format(package): _manifest_module(manifest),
        "tests/test_manifest.py": _manifest_test(identity),
    }


def _is_canonical_absolute_path(value: object) -> bool:
    return (
        type(value) is str
        and 0 < len(value) <= _MAX_PATH_LENGTH
        and "\x00" not in value
        and os.path.isabs(value)
        and os.path.normpath(value) == value
    )


def _path_exists_or_is_symlink(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        _raise_scaffold_error(ProductPackScaffoldErrorCode.UNSAFE_OUTPUT_PATH)
    return True


def _is_real_directory_without_symlink_ancestors(path: Path) -> bool:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        try:
            mode = current.lstat().st_mode
        except OSError:
            return False
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            return False
    return True


def _validate_target(output_directory: str) -> Path:
    target = Path(output_directory)
    if not _is_real_directory_without_symlink_ancestors(target.parent):
        _raise_scaffold_error(ProductPackScaffoldErrorCode.UNSAFE_OUTPUT_PATH)
    if _path_exists_or_is_symlink(target):
        _raise_scaffold_error(ProductPackScaffoldErrorCode.TARGET_EXISTS)
    return target


def _write_files(root: Path, files: Dict[str, str]) -> None:
    for relative_path in sorted(files):
        destination = root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(files[relative_path])


def _remove_private_temporary_directory(path: Path, parent: Path) -> None:
    if path.parent == parent and path.name.startswith(".pmqa-scaffold-"):
        shutil.rmtree(path, ignore_errors=True)


def scaffold_product_pack(
    request: ProductPackScaffoldRequest,
) -> ProductPackScaffoldResult:
    """Create one deterministic scaffold and publish it with one rename."""

    if type(request) is not ProductPackScaffoldRequest:
        _raise_scaffold_error(ProductPackScaffoldErrorCode.INVALID_REQUEST)
    target = _validate_target(request.output_directory)
    files = _render_files(request.manifest)
    temporary = None
    failure = None
    try:
        temporary = Path(
            tempfile.mkdtemp(prefix=".pmqa-scaffold-", dir=str(target.parent))
        )
        _write_files(temporary, files)
        if _path_exists_or_is_symlink(target):
            _raise_scaffold_error(ProductPackScaffoldErrorCode.TARGET_EXISTS)
        os.rename(str(temporary), str(target))
        temporary = None
    except ProductPackScaffoldError:
        raise
    except MemoryError:
        raise
    except FileExistsError:
        failure = ProductPackScaffoldErrorCode.TARGET_EXISTS
    except OSError:
        failure = ProductPackScaffoldErrorCode.GENERATION_FAILED
    finally:
        if temporary is not None:
            _remove_private_temporary_directory(temporary, target.parent)
    if failure is not None:
        _raise_scaffold_error(failure)

    identity = _derive_identity(request.manifest)
    return ProductPackScaffoldResult(
        scaffold_version=PRODUCT_PACK_SCAFFOLD_VERSION,
        distribution_name=identity.distribution_name,
        python_package_name=identity.python_package_name,
        generated_files=tuple(sorted(files)),
    )


class _DuplicateJSONKey(ValueError):
    pass


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJSONKey()
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    _ = value
    raise _DuplicateJSONKey()


def _read_required_files(
    root: Path,
    relative_paths: Tuple[str, ...],
) -> Optional[Dict[str, str]]:
    values = {}
    for relative_path in relative_paths:
        path = root / relative_path
        try:
            current = root
            for part in Path(relative_path).parts[:-1]:
                current = current / part
                parent_mode = current.lstat().st_mode
                if stat.S_ISLNK(parent_mode) or not stat.S_ISDIR(parent_mode):
                    return None
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
                return None
            if path.stat().st_size > _MAX_CONTROL_FILE_BYTES:
                return None
            values[relative_path] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return None
    return values


def _conformance_failure(
    code: ProductPackSourceConformanceErrorCode,
) -> ProductPackSourceConformanceResult:
    return ProductPackSourceConformanceResult(False, code)


def validate_product_pack_source(
    source_directory: str,
    expected_manifest: Optional[ProductPackManifest] = None,
) -> ProductPackSourceConformanceResult:
    """Validate scaffold-owned control files without executing product code."""

    if (
        not _is_canonical_absolute_path(source_directory)
        or (
            expected_manifest is not None
            and type(expected_manifest) is not ProductPackManifest
        )
    ):
        return _conformance_failure(
            ProductPackSourceConformanceErrorCode.INVALID_REQUEST
        )
    root = Path(source_directory)
    if not _is_real_directory_without_symlink_ancestors(root):
        return _conformance_failure(
            ProductPackSourceConformanceErrorCode.INVALID_LAYOUT
        )
    base_files = (
        ".gitignore",
        "README.md",
        "bridge/package.json",
        "bridge/src/capture_backend.ts",
        "bridge/src/main.ts",
        "bridge/src/protocol.ts",
        "bridge/tsconfig.json",
        "product-pack.json",
        "pyproject.toml",
        "tests/test_manifest.py",
    )
    files = _read_required_files(root, base_files)
    if files is None:
        return _conformance_failure(
            ProductPackSourceConformanceErrorCode.INVALID_LAYOUT
        )
    try:
        payload = json.loads(
            files["product-pack.json"],
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        manifest = ProductPackManifest.from_dict(payload)
    except (ValueError, RecursionError, OverflowError):
        return _conformance_failure(
            ProductPackSourceConformanceErrorCode.INVALID_MANIFEST
        )
    if files["product-pack.json"] != _canonical_json(manifest.to_dict()):
        return _conformance_failure(
            ProductPackSourceConformanceErrorCode.INVALID_MANIFEST
        )
    if expected_manifest is not None and manifest != expected_manifest:
        return _conformance_failure(
            ProductPackSourceConformanceErrorCode.MANIFEST_MISMATCH
        )

    identity = _derive_identity(manifest)
    package_files = (
        "src/{}/__init__.py".format(identity.python_package_name),
        "src/{}/manifest.py".format(identity.python_package_name),
    )
    python_files = _read_required_files(root, package_files)
    if python_files is None:
        return _conformance_failure(
            ProductPackSourceConformanceErrorCode.INVALID_PYTHON_DISTRIBUTION
        )
    expected_files = _render_files(manifest)
    for relative_path in package_files + ("pyproject.toml", "tests/test_manifest.py"):
        actual = (
            python_files[relative_path]
            if relative_path in python_files
            else files[relative_path]
        )
        if actual != expected_files[relative_path]:
            return _conformance_failure(
                ProductPackSourceConformanceErrorCode.INVALID_PYTHON_DISTRIBUTION
            )

    bridge_files = (
        "bridge/package.json",
        "bridge/tsconfig.json",
        "bridge/src/protocol.ts",
        "bridge/src/capture_backend.ts",
        "bridge/src/main.ts",
    )
    if any(files[path] != expected_files[path] for path in bridge_files):
        return _conformance_failure(
            ProductPackSourceConformanceErrorCode.INVALID_BRIDGE_SOURCE
        )
    return ProductPackSourceConformanceResult(True, None)


def _raise_scaffold_error(code: ProductPackScaffoldErrorCode) -> None:
    raise ProductPackScaffoldError(code) from None


__all__ = [
    "PRODUCT_PACK_SCAFFOLD_VERSION",
    "ProductPackScaffoldError",
    "ProductPackScaffoldErrorCode",
    "ProductPackScaffoldRequest",
    "ProductPackScaffoldResult",
    "ProductPackSourceConformanceErrorCode",
    "ProductPackSourceConformanceResult",
    "scaffold_product_pack",
    "validate_product_pack_source",
]
