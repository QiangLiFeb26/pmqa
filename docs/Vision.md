# PMQA Vision

PMQA stands for Product Memory QA Agent.

PMQA helps QA engineers preserve and reuse product knowledge, historical defects, business rules, testing guidance, feature ownership, and risk signals so testing decisions are grounded in the product's actual history.

## 1. Problem

QA knowledge is often scattered across tickets, release notes, chat threads, test cases, incident reports, tribal memory, and individual experience. Important context about past defects, fragile workflows, business rules, and feature ownership can be difficult to find when planning or executing testing.

This creates several recurring problems:

- QA engineers repeat investigation work because prior knowledge is hard to retrieve.
- Historical bugs are forgotten after they are fixed, even though they are strong signals for future risk.
- Product-specific rules live inside people, stale documents, or isolated test cases instead of a reusable memory layer.
- Testing effort can drift toward exhaustive coverage attempts instead of focused, risk-based decisions.
- New QA engineers need significant time to build product context before they can test confidently.

## 2. Target Users

PMQA is designed primarily for QA engineers who test complex products over time and need product memory at the moment of testing.

Secondary users include:

- QA leads who want better continuity across releases and team members.
- Product managers who need clearer visibility into quality risks and historical defect patterns.
- Engineers who want QA feedback informed by prior bugs, business rules, and ownership context.
- New team members who need to ramp up on product behavior and risk areas.

## 3. Product Vision

PMQA should become a product memory companion for QA work.

Its role is not to replace QA judgment, but to strengthen it. PMQA should help testers ask better questions, remember relevant history, identify risky areas, and connect current changes to previous product behavior.

The long-term vision is an agent that can answer questions such as:

- What historical bugs are relevant to this feature?
- What business rules should I remember before testing this workflow?
- Which areas are risky based on past defects or ownership changes?
- What should a QA engineer pay attention to before signing off this release?
- Who owns this feature, and what context should I know before escalating?

PMQA should make product knowledge easier to preserve, retrieve, and apply during real QA workflows.

## 4. Core Principles

### Product Knowledge Lives in Product Packs

Product-specific knowledge should be isolated in product packs. A product pack
represents the memory and context for a specific product, domain, team, or
system and may compose adapters at its external boundaries.

This keeps PMQA flexible. The core system should not hard-code product facts, feature names, business rules, or historical bugs.

### QA Skills Are Reusable

QA skills should be separate from product knowledge. Skills such as risk analysis, regression planning, bug pattern recognition, exploratory testing guidance, and release review should be reusable across products.

The same QA skill should be able to operate on different product memories
through different product packs.

### Historical Bugs Are Testing Assets

Past defects are not just closed tickets. They are signals about where the product has failed before, where requirements were misunderstood, and where risk may return.

PMQA should treat historical bugs as durable testing assets that can inform future coverage, regression focus, and risk assessment.

### Risk-Based Testing Comes First

PMQA should prioritize risk-based testing over exhaustive testing. The goal is not to generate the largest possible set of tests, but to help QA engineers focus on the highest-value areas.

Useful PMQA output should help answer: "What matters most to test, and why?"

### Start With Product Memory

The MVP should focus on product memory, retrieval, and QA reasoning support. Full automation generation can come later.

The first version should make stored product knowledge useful before attempting to produce end-to-end automated test suites.

## 5. MVP Scope

The MVP should focus on building a practical Product Memory layer for QA.

In scope:

- Store product-specific knowledge in product packs.
- Capture business rules, feature notes, ownership context, and testing guidance.
- Capture historical bugs as reusable risk signals.
- Retrieve relevant product memory for a feature, workflow, bug, or release.
- Support risk-based QA prompts and summaries.
- Keep QA skills reusable and separate from product packs.
- Provide enough structure for future expansion without building full automation yet.

The MVP should help QA engineers answer context-heavy testing questions faster and with better recall.

## 6. Non-Goals

The MVP should not attempt to become a full test automation platform.

Non-goals include:

- Generating complete end-to-end automation suites.
- Replacing QA engineers or QA judgment.
- Becoming a general project management system.
- Becoming a source-of-truth replacement for issue trackers, test management tools, or product documentation.
- Hard-coding one product's rules into the PMQA core.
- Optimizing for exhaustive test generation instead of risk-based testing support.

## 7. Future Direction

After the Product Memory foundation is useful, PMQA can expand toward deeper QA assistance.

Future directions may include:

- Product-pack templates for different products, domains, and teams.
- Integrations with issue trackers, test case systems, documentation tools, and release notes.
- Defect pattern analysis across historical bugs.
- Risk scoring for features, workflows, and releases.
- Suggested regression focus based on change context and product history.
- Test idea generation grounded in product memory.
- Automation recommendations where product knowledge and QA skills indicate high value.
- Team-level memory workflows for review, curation, and ownership.

The guiding direction should remain clear: PMQA should make QA smarter by preserving product memory and applying it through reusable QA skills.
