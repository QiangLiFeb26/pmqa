# Product Pack Adoption Architecture

## Status

Task 5A.1 records the experimental architecture decision and manifest contract,
Task 5A.2 completes explicit external manifest loading, and Task 5A.3 completes
Bridge Protocol v1 contracts on the cumulative branch. Task 5A.4 adds bounded
process transport and is ready for architecture review. These checkpoints are
not a stable Product Pack SDK or a commitment that API version 1 is complete.

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
4. A future TypeScript bridge protocol will have its own independent version.
   No bridge field or protocol is defined in the manifest today.

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

No Playwright Product Pack, template, scaffold, SauceDemo migration, or MDE
integration is implemented by Task 5A.4.

## Adoption sequence

The planned evidence-driven sequence is:

1. experimental manifest;
2. explicit external loading;
3. versioned TypeScript bridge;
4. scaffolding and conformance tooling;
5. SauceDemo migration;
6. company-side, read-only MDE pilot; and
7. API v1 stabilization after evidence from both SauceDemo and MDE.

Task 5A.4 is ready for architecture review and is not merged or complete on
`main`. Task 5A.5 and later steps have not started. Task 6 and Task 7 have not
started.
