# SauceDemo External Product Pack

This is an experimental, explicitly selected Product Pack used to validate the
PMQA Product Pack architecture. It is an example outside the PMQA distribution,
not a stable SDK and not an automatically discovered plugin.

The Python distribution exposes only the plain `saucedemo` manifest entry
point. The consumer-owned TypeScript backend uses direct, exactly pinned
Playwright and Bridge Protocol v1. It accepts only the ordered action-plan
prefix `inspect_login_page`, `login`, `verify_inventory_page`, and
`inspect_inventory_item`. Protocol JSON is written only to stdout; failures use
the bounded bridge vocabulary and never include raw exception text.

Product Pack API version and Bridge Protocol version are independent. The
bridge request ID uses the bounded JSON-only transport-correlation policy so
the established colon-composed Task 5 Tool invocation and downstream domain
identities remain unchanged; manifest and action identifiers stay stricter.
Structural fingerprints preserve array order, sort object keys, serialize
compact JSON without ASCII escaping, encode UTF-8, and hash with SHA-256. The
shared fixed vector is `tests/structural-fingerprint-v1.json`; default tests
verify Python/offline parity, while opt-in compiled Node and live Playwright
tests prove actual cross-language parity.

The bridge reads credentials only from its child-process environment:

- `SAUCEDEMO_USERNAME`
- `SAUCEDEMO_PASSWORD`
- optional `SAUCEDEMO_BASE_URL`

PMQA does not read, validate, serialize, persist, or print these values. Do not
store them in this source tree. Node installation and TypeScript compilation
are explicit operator actions; default Python tests perform neither. Build in a
temporary copy so `node_modules` and `bridge/dist` never enter the repository.

Task 5A.1–5A.6 have completed cumulative architecture review. The existing
direct Python Task 5 SauceDemo workflow and public
`pmqa task5-demo --product demo` command remain the authoritative stable
baseline. This external pack remains an architecture-validation example
outside the PMQA wheel; it does not redirect or replace the public command.
The Product Pack API remains experimental rather than stable SDK v1. After
the Task 5A merge through PR #22, Task 5B is the not-started placeholder for a
company-side, read-only MDE pilot. API v1 stabilization waits for evidence from
both SauceDemo and MDE. Task 5B implementation, Task 6, and Task 7 have not
started.
