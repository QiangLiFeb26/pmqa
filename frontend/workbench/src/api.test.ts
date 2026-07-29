import { afterEach, describe, expect, it, vi } from "vitest";

import { APIClient } from "./api";

const sessionToken = "a".repeat(43);
const csrfToken = "b".repeat(43);

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("authenticated API client", () => {
  it("sends exact Bearer authentication on reads without CSRF", async () => {
    const fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ schema_version: "1", readiness: "ready" }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetch);
    const client = new APIClient({ sessionToken, csrfToken });

    await client.health();

    const [, init] = fetch.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Headers;
    expect(headers.get("Authorization")).toBe(`Bearer ${sessionToken}`);
    expect(headers.has("X-PMQA-CSRF-Token")).toBe(false);
    expect(init.credentials).toBe("omit");
  });

  it("sends the exact CSRF token only on mutations", async () => {
    const fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          schema_version: "1",
          session: {
            schema_version: "1",
            session_id: "conversation.session.1",
            revision: 1,
          },
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetch);
    const client = new APIClient({ sessionToken, csrfToken });

    await client.createSession("30_days");

    const [path, init] = fetch.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Headers;
    expect(path).toBe("/api/v1/sessions");
    expect(init.method).toBe("POST");
    expect(headers.get("Authorization")).toBe(`Bearer ${sessionToken}`);
    expect(headers.get("X-PMQA-CSRF-Token")).toBe(csrfToken);
    expect(headers.get("Content-Type")).toBe("application/json");
  });
});
