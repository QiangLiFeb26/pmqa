import { createHash } from "node:crypto";
import {
  chromium,
  type Browser,
  type BrowserContext,
  type Page,
} from "playwright";

import type { ProductCaptureBackend } from "./capture_backend.js";
import type {
  BridgeFailureCode,
  BridgeRequestV1,
  BridgeResponseV1,
  ExplorationEvidenceV1,
  LocatorCandidateObservationV1,
  ObservedElementV1,
  ObservedPageV1,
} from "./protocol.js";
import { structuralFingerprint } from "./fingerprint.js";

const ACTIONS = [
  "inspect_login_page",
  "login",
  "verify_inventory_page",
  "inspect_inventory_item",
] as const;
const IDENTIFIER = /^[a-z0-9]+(?:[._-][a-z0-9]+)*$/;
const CORRELATION_IDENTIFIER =
  /^[a-z0-9]+(?:[._-][a-z0-9]+)*(?::[a-z0-9]+(?:[._-][a-z0-9]+)*)*$/;
const CANONICAL_TIME =
  /^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{6})?Z$/;

class SauceDemoCaptureBackend implements ProductCaptureBackend {
  async capture(request: BridgeRequestV1): Promise<BridgeResponseV1> {
    if (!validRequest(request)) {
      return failure(request, "protocol_failure");
    }
    if (!validActionPlan(request.action_plan)) {
      return failure(request, "action_plan_rejected");
    }

    let browser: Browser | undefined;
    let context: BrowserContext | undefined;
    let page: Page | undefined;
    try {
      const username = process.env.SAUCEDEMO_USERNAME;
      const password = process.env.SAUCEDEMO_PASSWORD;
      if (!username || !password) {
        return failure(request, "exploration_failed");
      }
      const baseUrl = process.env.SAUCEDEMO_BASE_URL ?? "https://www.saucedemo.com";
      browser = await chromium.launch({ headless: true });
      context = await browser.newContext();
      page = await context.newPage();
      await page.goto(baseUrl + "/");

      const pages: ObservedPageV1[] = [];
      const elements: ObservedElementV1[] = [];
      const locatorCandidates: LocatorCandidateObservationV1[] = [];
      const interactions = [];
      for (const action of request.action_plan) {
        if (action === "inspect_login_page") {
          await page.locator("[data-test='username']").waitFor();
          pages.push(await observedPage(page, "page.login"));
          elements.push(
            observedElement("element.username", "textbox", "Username", "username", null, "text"),
            observedElement("element.password", "textbox", "Password", "password", null, "password"),
            observedElement("element.login", "button", "Login", "login-button", "Login", null),
          );
          locatorCandidates.push(
            locator("locator.username", "element.username", "username"),
            locator("locator.password", "element.password", "password"),
            locator("locator.login", "element.login", "login-button"),
          );
        } else if (action === "login") {
          await page.locator("[data-test='username']").fill(username);
          await page.locator("[data-test='password']").fill(password);
          await page.locator("[data-test='login-button']").click();
          await page.waitForURL("**/inventory.html");
          interactions.push({
            interaction_id: "interaction.login",
            source_page_id: "page.login",
            target_element_id: "element.login",
            action: "click",
            outcome_type: "navigation",
            outcome_value: "/inventory.html",
          });
        } else if (action === "verify_inventory_page") {
          await page.locator("[data-test='title']").waitFor();
          pages.push(await observedPage(page, "page.inventory"));
          elements.push(
            observedElement(
              "element.inventory_title",
              "heading",
              "Products",
              "title",
              "Products",
              null,
              "page.inventory",
            ),
          );
          locatorCandidates.push(
            locator("locator.inventory_title", "element.inventory_title", "title"),
          );
        } else {
          await page.locator("[data-test='inventory-item']").first().waitFor();
        }
      }

      const capturedAt = canonicalNowAtLeast(request.requested_at);
      const evidence: ExplorationEvidenceV1 = {
        schema_version: "1",
        evidence_id: evidenceId(request),
        workflow_id: request.workflow_id,
        product_id: request.product_id,
        source: {
          source_type: "typescript-playwright",
          tool_id: request.tool_id,
          capture_id: request.request_id,
        },
        captured_at: capturedAt,
        pages,
        elements,
        locator_candidates: locatorCandidates,
        interactions,
      };
      return {
        ...responseIdentity(request),
        status: "succeeded",
        completed_at: canonicalNowAtLeast(capturedAt),
        evidence,
        failure_code: null,
      };
    } catch {
      return failure(request, "exploration_failed");
    } finally {
      await closeQuietly(page);
      await closeQuietly(context);
      await closeQuietly(browser);
    }
  }
}

function validRequest(request: BridgeRequestV1): boolean {
  if (typeof request !== "object" || request === null) return false;
  const keys = Object.keys(request).sort();
  const expected = [
    "action_plan", "operation", "pack_id", "product_id", "protocol_version",
    "request_id", "requested_at", "tool_id", "workflow_id",
  ];
  if (JSON.stringify(keys) !== JSON.stringify(expected)) return false;
  const identifiers = [
    request.workflow_id,
    request.product_id,
    request.pack_id,
    request.tool_id,
  ];
  return request.protocol_version === "1"
    && request.operation === "exploration_capture"
    && request.product_id === "demo"
    && request.pack_id === "saucedemo"
    && request.tool_id === "playwright.saucedemo_explore"
    && typeof request.request_id === "string"
    && request.request_id.length <= 256
    && CORRELATION_IDENTIFIER.test(request.request_id)
    && identifiers.every((value) =>
      typeof value === "string" && value.length <= 64 && IDENTIFIER.test(value))
    && typeof request.requested_at === "string"
    && CANONICAL_TIME.test(request.requested_at)
    && Array.isArray(request.action_plan);
}

function validActionPlan(actions: string[]): boolean {
  return actions.length > 0
    && actions.length <= ACTIONS.length
    && actions.every((action, index) => action === ACTIONS[index])
    && new Set(actions).size === actions.length;
}

function responseIdentity(request: BridgeRequestV1) {
  return {
    protocol_version: "1" as const,
    request_id: request.request_id,
    workflow_id: request.workflow_id,
    product_id: request.product_id,
    pack_id: request.pack_id,
    tool_id: request.tool_id,
    operation: "exploration_capture" as const,
  };
}

function failure(
  request: BridgeRequestV1,
  failureCode: BridgeFailureCode,
): BridgeResponseV1 {
  return {
    ...responseIdentity(request),
    status: "failed",
    completed_at: canonicalNowAtLeast(request.requested_at),
    evidence: null,
    failure_code: failureCode,
  };
}

function observedElement(
  elementId: string,
  role: string,
  accessibleName: string,
  testId: string,
  visibleText: string | null,
  inputType: string | null,
  pageId = "page.login",
): ObservedElementV1 {
  const attributes = [{ name: "data-test", value: testId }];
  if (inputType !== null) attributes.push({ name: "type", value: inputType });
  return {
    element_id: elementId,
    page_id: pageId,
    role,
    accessible_name: accessibleName,
    visible_text: visibleText,
    attributes,
  };
}

function locator(
  locatorId: string,
  elementId: string,
  value: string,
): LocatorCandidateObservationV1 {
  return {
    locator_candidate_id: locatorId,
    element_id: elementId,
    strategy: "data-test",
    value,
    priority: 1,
  };
}

async function observedPage(page: Page, pageId: string): Promise<ObservedPageV1> {
  const structure = await page.locator("body").evaluate((body) =>
    Array.from(body.querySelectorAll("[data-test]")).map((element) => ({
      tag: element.tagName.toLowerCase(),
      dataTest: element.getAttribute("data-test"),
      type: element.getAttribute("type"),
      text: element.matches("input")
        ? null
        : (element.textContent ?? "").trim().slice(0, 200),
    })),
  );
  return {
    page_id: pageId,
    url: page.url(),
    title: await page.title(),
    structural_fingerprint: structuralFingerprint(structure),
  };
}

function evidenceId(request: BridgeRequestV1): string {
  return "evidence.saucedemo." + createHash("sha256")
    .update(request.workflow_id + "\0" + request.request_id)
    .digest("hex")
    .slice(0, 24);
}

function canonicalNowAtLeast(minimum: string): string {
  const minimumMillis = Date.parse(minimum);
  const millis = Number.isFinite(minimumMillis)
    ? Math.max(Date.now(), minimumMillis)
    : Date.now();
  return new Date(millis).toISOString().replace(/\.(\d{3})Z$/, ".$1000Z");
}

async function closeQuietly(
  resource: Browser | BrowserContext | Page | undefined,
): Promise<void> {
  if (resource === undefined) return;
  try {
    await resource.close();
  } catch {
    // Resource release must not replace the bounded bridge response.
  }
}

export function createProductCaptureBackend(): ProductCaptureBackend {
  return new SauceDemoCaptureBackend();
}
