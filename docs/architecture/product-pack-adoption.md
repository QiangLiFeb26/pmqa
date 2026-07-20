# Product Pack Adoption Architecture

## Status

Task 5A.1 records an experimental architecture decision and manifest contract.
It is an implementation checkpoint ready for architecture review, not a stable
Product Pack SDK or a commitment that API version 1 is complete.

## Decision

PMQA uses three logical boundaries:

```text
PMQA Core
    <- stable Product Pack API
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
identity and a bounded capability declaration. It does not locate, load,
register, configure, or execute a Product Pack.

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
- A later task must make external loading an explicit operator
  configuration.
- PMQA must not automatically scan arbitrary directories for Product Packs.

Task 5A.1 implements none of the external loading, discovery, registry, or
repository integration described as future work.

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

It has no free-form metadata or configuration mapping. Its bounded capability
vocabulary covers exploration capture, knowledge mapping, knowledge
validation, test generation, and test inventory. It does not grant access to
credentials, repositories, providers, commands, or runtime objects.

The exact-field policy and strict validation prevent credentials, tokens,
passwords, cookies, environment values, base URLs, selectors, DOM or HTML,
filesystem and repository paths, callables, subprocess handles, browser
objects, arbitrary entry points, command lines, and free-form configuration
from entering the manifest. Validation errors hide input values. Importing the
contract performs no file reads, environment access, discovery, or
registration.

## Future TypeScript execution boundary

Task 5A.3 will define the direction of a versioned TypeScript Playwright
bridge. Credentials must be resolved inside the TypeScript/product execution
boundary. Python PMQA must not receive credentials, cookies, storage state,
complete DOM content, or browser handles. Only versioned, structured, bounded,
safe JSON observations may cross that boundary.

Bridge runner selection, timeouts, output bounds, process isolation, and the
protocol itself belong to Task 5A.3 and are not implemented here.

## Adoption sequence

The planned evidence-driven sequence is:

1. experimental manifest;
2. explicit external loading;
3. versioned TypeScript bridge;
4. scaffolding and conformance tooling;
5. SauceDemo migration;
6. company-side, read-only MDE pilot; and
7. API v1 stabilization after evidence from both SauceDemo and MDE.

Task 5A.2 and later steps have not started. Task 6 and Task 7 have not started.
