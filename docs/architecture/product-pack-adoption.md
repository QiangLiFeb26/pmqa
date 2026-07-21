# Product Pack Adoption Architecture

## Status

Task 5A.1 records the experimental architecture decision and manifest contract,
Task 5A.2 completes explicit external manifest loading, and Task 5A.3 completes
Bridge Protocol v1 contracts on the cumulative branch. Task 5A.4 completes
bounded process transport, and Task 5A.5 adds deterministic scaffolding and
offline source conformance. Task 5A.6 adds an external SauceDemo vertical slice
for architecture validation. Task 5A.1–5A.6 have completed cumulative
architecture review and are ready for the final Task 5A PR. These checkpoints
are not a stable Product Pack SDK or a commitment that API version 1 is
complete.

## Decision

PMQA uses three logical boundaries:

```text
PMQA Core
    <- versioned Product Pack API
Private/external Product Pack
    <- safe adapter or future versioned bridge
Consumer product and existing E2E automation
```

These boundaries describe ownership and dependency direction. They do not
require every consuming team to create or maintain three repositories. A
long-term deployment may use one general PMQA Core repository, one
company-level private Product Pack repository, and the existing product
repository. Consumer teams would normally maintain only their owned directory
inside the private Product Pack repository.

The Task 5A.1 manifest is deliberately small. It contains only versioned
identity and a bounded capability declaration. Task 5A.2 can load that metadata
from one explicitly selected installed distribution; it does not register,
configure, or execute product adapters.

## Ownership

The PMQA platform team owns:

- core contracts;
- Product Pack API design and versioning;
- conformance tests;
- the security boundary; and
- generic tooling and templates.

The consumer product team owns:

- product manifest values;
- product configuration;
- the safe action vocabulary;
- product adapters;
- TypeScript Playwright capture implementation;
- domain mapping and validation; and
- product-specific evaluation data.

## Dependency direction

- PMQA Core must not depend on, search for, or eagerly import a concrete
  Product Pack.
- Product Packs may depend on public PMQA contracts.
- A product repository does not need to depend on Python PMQA.
- An IDE multi-root workspace is a development convenience, not a runtime
  dependency.
- A Product Pack must not import product source across repositories through
  relative filesystem paths.
- External loading requires an explicit operator-approved distribution name
  and complete expected manifest.
- PMQA must not automatically scan arbitrary directories for Product Packs.

Task 5A.2 implements no automatic discovery, registry, arbitrary-path loading,
or repository integration.

## Explicit external manifest loading

Task 5A.2 inspects only the installed distribution explicitly named in a
`ProductPackLoadRequest`. Python distribution names are normalized to lowercase
ASCII so `.`, `_`, and repeated `-` aliases have one hyphenated form.
The loader never enumerates global entry points or installed distributions,
scans directories, changes `sys.path`, installs a package, or loads a repository
path.

The fixed entry-point group is `pmqa.product_packs`. Within the selected
distribution, exactly one entry point must have a name equal to the expected
manifest's `pack_id`. Its value must resolve to a plain dictionary. PMQA
reconstructs that dictionary through `ProductPackManifest.from_dict()` and
requires complete contract equality with the operator-approved expected
manifest. The immutable result retains only the canonical distribution name
and validated manifest; it is not workflow state. The result contract enforces
the same canonical distribution-name policy and requires an exact
`ProductPackManifest` even when constructed directly.

Resolved distribution metadata is also external boundary data. Failures while
accessing or iterating entry points, or while reading their group and name,
become one bounded product-neutral loader failure without exposing the
distribution, entry point, path, or underlying exception.

The manifest payload is untrusted serialized data. In contrast, the explicitly
selected installed Python distribution is operator-approved trusted code:
calling `EntryPoint.load()` performs normal Python import execution and is not
a sandbox. PMQA does not make arbitrary packages safe. Future TypeScript
execution isolation is separate Task 5A.3 work.

## Version model

Product Pack adoption has four independent version axes:

1. `schema_version` versions the serialized manifest shape. Task 5A.1 accepts
   only manifest schema `"1"`.
2. `product_pack_api_version` declares the PMQA Product Pack API expected by a
   pack. The experimental manifest currently accepts only `"1"`; this does
   not mean the API has been stabilized.
3. `pack_version` versions the Product Pack itself and must be a canonical
   Semantic Versioning 2.0.0 value.
4. `protocol_version` versions the language-neutral TypeScript bridge wire
   contract. Bridge Protocol v1 is independently enforced and is not a
   manifest field.

Keeping these axes separate prevents manifest-format, API, pack-release, and
transport compatibility from being conflated.

## Manifest security boundary

The manifest is immutable, JSON-compatible, deterministic, and declarative.
Its exact fields are:

- `schema_version`;
- `product_pack_api_version`;
- `pack_id`;
- `pack_version`;
- `product_id`;
- `display_name`; and
- `capabilities`.

It has no credential, command, path, runtime-object, free-form metadata, or
configuration field. Its bounded capability vocabulary covers exploration
capture, knowledge mapping, knowledge validation, test generation, and test
inventory; it grants no repository, provider, command-execution, or credential
capability.

All allowed field values are public, non-sensitive metadata. Product Pack
authors must not encode secrets in `display_name`, identifiers, versions,
capabilities, or any other allowed value. The manifest contract is not a
secret scanner, DLP system, or PHI scrubber. Exact-field and strict validation
reject undeclared fields and invalid runtime shapes; they do not detect secret
content inside an otherwise valid string.

Trusted internal code may construct `ProductPackManifest` directly and receive
detailed Pydantic validation failures. Serialized or untrusted private/external
manifest data must instead pass through `ProductPackManifest.from_dict()`,
which converts expected validation failures into the fixed, bounded
`ProductPackManifestValidationError`. That safe domain error can cross an
application or CLI boundary. Raw external payloads and raw Pydantic structured
errors must not be logged. The Task 5A.2 loader must use `from_dict()` rather
than the constructor or `model_validate()`.

Importing the contract performs no file reads, environment access, discovery,
or registration.

## Future TypeScript execution boundary

Task 5A.3 defines the language-neutral Bridge Protocol v1 contracts. Version 1
supports only `exploration_capture`: an immutable, bounded action plan crosses
to the future product boundary, with at most 32 canonical action identifiers,
and exactly one validated
`ExplorationEvidence` may return on success. Credentials, arbitrary
configuration or environment data, raw DOM/HTML, browser handles, commands,
paths, and runtime objects are not protocol fields. Structured locator
observations already permitted by `ExplorationEvidence` remain valid evidence.

Bridge protocol version, manifest schema version, Product Pack API version,
and Product Pack version are independent compatibility axes. The canonical
versioned JSON schema is mechanically checked against the Python contracts and
packaged with PMQA.

Manifest, product, pack, workflow, Tool, and action identifiers retain the
strict lowercase Product Pack identifier policy. Bridge `request_id` is a
transport correlation value with its own maximum of 256 ASCII characters. It
accepts non-empty strict identifier components joined by `:` so the established
Task 5 Tool invocation can cross the wire unchanged; it rejects empty
components, whitespace, path separators, URLs, shell syntax, control
characters, non-ASCII text, and prohibited semantic components. It remains
JSON data only and is never selected as an executable, argument, path,
environment-variable name, or shell command.

## Bounded bridge process transport

Task 5A.4 runs one explicitly operator-selected executable and compiled bridge
artifact without shell expansion, PATH search, fallback commands, working
directory search, or manifest-provided commands. Its deterministic argument
vector contains only those two approved absolute paths. One compact canonical
Bridge Protocol v1 request is written to stdin; stdout must contain exactly one
bounded canonical protocol response. Stderr is bounded and drained but never
crosses the public boundary.

Default limits are 30 seconds, 256 KiB request bytes, 2 MiB stdout, and 256 KiB
stderr. Configuration caps are 300 seconds, 1 MiB request bytes, 8 MiB stdout,
and 1 MiB stderr. Timeout and stream-limit failures terminate and reap the
process, with process-group descendant cleanup on POSIX systems.

Process configuration is runtime-only trusted operator input. It has no
serialization API and cannot enter the manifest, protocol payloads,
`WorkflowState`, persisted knowledge, or public errors. The child inherits its
normal execution environment; PMQA neither inspects credentials nor serializes
environment data. The private product boundary remains responsible for
credential resolution. This transport provides bounded execution and strict
validation, not a security sandbox.

The historical Task 5A.4 checkpoint itself implemented no Playwright Product
Pack, template, scaffold, SauceDemo migration, or MDE integration.

## External source scaffolding and conformance

Task 5A.5 creates a minimal external Python manifest distribution and direct
TypeScript bridge source tree only in the absolute target explicitly selected
by the operator. It builds in a private sibling temporary directory and
publishes with a final rename; it never merges into or overwrites an existing
target. A separate private Product Pack source location is recommended, and
the scaffold never writes into a product repository unless the operator
deliberately selects that location.

The generated Python entry point exposes only the canonical plain manifest
dictionary. Product Pack `pack_version` remains canonical SemVer and is stored
unchanged in that manifest. The scaffold request separately requires a
canonical PEP 440 `distribution_version`, which alone becomes
`project.version`; the loader does not compare the two version axes.

The TypeScript source fixes Bridge Protocol v1 and separates ownership. The
protocol declarations, capture-backend interface and fail-closed placeholder,
and bounded stdin/stdout adapter are scaffold-owned controls. The separate
consumer-owned `product_backend.ts` exports `createProductCaptureBackend()`.
Initially it returns the placeholder, which always produces a correlated
`protocol_failure` and cannot fabricate successful evidence. Consumers may
replace that implementation and add one exact direct Playwright dependency.
Playwright versions remain a consumer decision; Playwright MCP, install hooks,
URLs, local paths, Git dependencies, dynamic downloads, and unbounded versions
are rejected from package controls.

Offline source conformance reads only scaffold-owned required control files. It
checks the manifest, independently validated PEP 440 distribution metadata,
deterministic Python identity and entry point, supported protocol vocabulary,
strict scaffold-owned bridge controls, and the consumer backend factory shape
without importing, compiling, or running product code. Results distinguish
`placeholder` from `custom`; neither state claims runtime or semantic
verification. Conformance does not recursively inspect arbitrary consumer
source for secrets. Credentials remain exclusively in the consumer execution
environment. Scaffolding and conformance launch no browser, Node process,
external Product Pack, or network operation.

Publication uses an operating-system atomic no-replace directory primitive on
macOS and Linux where available, and the native no-replace rename behavior on
Windows. If a safe primitive is unavailable, scaffolding fails closed before
publication rather than using a clobber-capable fallback. A target that appears
during the final race window is preserved byte-for-byte and by identity. Atomic
visibility is therefore claimed only where the supported no-replace primitive
succeeds.

The temporary directory is created as an unpredictable, restrictive
`.pmqa-scaffold-*` sibling under the explicitly selected output parent. PMQA
records ownership descriptors and closes each exactly once. Successful
publication moves the directory into place and leaves no temporary sibling.
After any failure following temporary creation, PMQA deliberately performs no
recursive deletion, unlink, removal, rename, or replacement: it closes its
descriptors and preserves the private tree as a conservative orphan. This rule
also covers write failures, target races, unavailable publication primitives,
unexpected publication failures, and control-flow exceptions, eliminating a
check-to-delete race entirely. The orphan contains only generated scaffold
source; credentials, environment files, browser state, traces, runtime output,
and error details are never written there. Its path is not part of the public
result or safe error surface. Operators may inspect and manually remove an
orphan from the selected parent; PMQA provides no automatic orphan-cleanup
command.

## SauceDemo external validation slice

Task 5A.6 keeps the real example at
`examples/product_packs/saucedemo`, outside PMQA package discovery. Its Python
distribution exposes only the explicitly loaded plain manifest. The manifest
advertises only `exploration_capture`; mapping, validation, generation, and
inventory remain existing product-owned Python behavior rather than invented
Product Pack capabilities.

The generic `ProductPackExplorationTool` receives one exact
`LoadedProductPack`, one explicit runtime-only process configuration, one
canonical Tool identity, and an optional narrow test runner. It performs no
discovery, PATH search, environment inspection, agent construction, or product
import. Each valid Tool invocation becomes exactly one Bridge Protocol v1
request. The canonical Tool invocation ID is also the bridge request ID and
must equal the returned evidence capture ID.

Task 5 domain identities are compatibility data. The direct Explorer retains
its established colon-composed Tool invocation ID, and both direct and
external paths consequently retain the same evidence, candidate, knowledge
artifact, and validation IDs. External composition prevalidates that transport
correlation before any bridge process can launch.

Both product-owned capture implementations fingerprint the bounded structural
element array by preserving array order, sorting every object key
lexicographically, serializing compact JSON with deterministic strings and
nulls without ASCII escaping, encoding UTF-8, and emitting lowercase SHA-256
hex. Credentials, HTML, browser objects, timestamps, and environment values are
not hashed. A fixed non-sensitive vector covers null, empty, non-ASCII, login,
inventory, and deliberately noncanonical insertion order. Default offline
tests compare the direct path with a fake bridge; separate opt-in compiled Node
and live Playwright tests prove the real TypeScript vector, structural
fingerprints, timestamp-normalized verified knowledge, and byte-identical
generated tests.

The example consumer backend uses direct, exactly pinned TypeScript Playwright.
It implements only the ordered bounded SauceDemo actions and emits runtime-free
structured evidence. Credentials and optional base URL are read only inside
the child process; PMQA never copies them into protocol data, workflow state,
persisted knowledge, or errors. Node dependencies, compilation, and browser
execution are opt-in and use temporary output. Default tests remain offline,
browser-free, Node-free, and network-free.

A parallel `run_saucedemo_product_pack_workflow` composition wires the generic
Tool through the existing ToolRegistry and WorkflowRuntime to the unchanged
SauceDemo Explorer, Knowledge agent, Validator, Task 4 graph, strict artifact
handoff, storage, and generator. The existing direct Python Task 5 workflow and
public `pmqa task5-demo --product demo` command remain the authoritative stable
baseline. The external pack remains an architecture-validation example outside
the PMQA wheel and does not replace the public command.

## Adoption sequence

The planned evidence-driven sequence is:

1. experimental manifest;
2. explicit external loading;
3. versioned TypeScript bridge;
4. scaffolding and conformance tooling;
5. SauceDemo external validation slice;
6. company-side, read-only MDE pilot; and
7. API v1 stabilization after evidence from both SauceDemo and MDE.

Task 5A.1–5A.6 have completed cumulative architecture review and are ready for
the final Task 5A PR. The Product Pack API remains experimental; API v1
stabilization happens only after evidence from SauceDemo and the next
company-side, read-only MDE pilot. The MDE pilot, Task 6, and Task 7 have not
started.
