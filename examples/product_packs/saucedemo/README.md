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

The bridge reads credentials only from its child-process environment:

- `SAUCEDEMO_USERNAME`
- `SAUCEDEMO_PASSWORD`
- optional `SAUCEDEMO_BASE_URL`

PMQA does not read, validate, serialize, persist, or print these values. Do not
store them in this source tree. Node installation and TypeScript compilation
are explicit operator actions; default Python tests perform neither. Build in a
temporary copy so `node_modules` and `bridge/dist` never enter the repository.

The existing direct Python Task 5 SauceDemo workflow remains available as the
comparison reference until cumulative Task 5A review decides whether to switch
or retire it.
