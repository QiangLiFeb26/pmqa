import { afterEach, describe, expect, it, vi } from "vitest";

import {
  APIClient,
  type ConversationSession,
} from "./api";

const sessionToken = "a".repeat(43);
const csrfToken = "b".repeat(43);
const session: ConversationSession = {
  schema_version: "1",
  session_id: "conversation.session.1",
  revision: 3,
  status: "active",
  retention_policy: "30_days",
  connection_context_id: null,
  turn_ids: ["conversation.turn.1"],
  created_at: "2026-07-29T12:00:00Z",
  updated_at: "2026-07-29T12:01:00Z",
  expires_at: "2026-08-28T12:01:00Z",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

function clientAndFetch() {
  const fetch = vi.fn().mockImplementation(() =>
    Promise.resolve(
      new Response(JSON.stringify({ schema_version: "1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
  vi.stubGlobal("fetch", fetch);
  return {
    client: new APIClient({ sessionToken, csrfToken }),
    fetch,
  };
}

function assertRequest(
  fetch: ReturnType<typeof vi.fn>,
  {
    path,
    method,
    body,
    mutation,
  }: {
    path: string;
    method: string;
    body?: unknown;
    mutation: boolean;
  },
) {
  expect(fetch).toHaveBeenCalledOnce();
  const [actualPath, init] = fetch.mock.calls[0] as [string, RequestInit];
  const headers = init.headers as Headers;
  expect(actualPath).toBe(path);
  expect(init.method ?? "GET").toBe(method);
  expect(init.body).toBe(
    body === undefined ? undefined : JSON.stringify(body),
  );
  expect(headers.get("Authorization")).toBe(`Bearer ${sessionToken}`);
  expect(headers.get("X-PMQA-CSRF-Token")).toBe(
    mutation ? csrfToken : null,
  );
  expect(headers.has("Cookie")).toBe(false);
  expect(headers.get("Content-Type")).toBe(
    body === undefined ? null : "application/json",
  );
  expect(init.credentials).toBe("omit");
  expect(init.cache).toBe("no-store");
  expect(init.referrerPolicy).toBe("no-referrer");
}

describe("authenticated API client", () => {
  it.each([
    ["health", "/api/v1/health"],
    ["workflows", "/api/v1/workflows"],
    ["sessions", "/api/v1/sessions"],
  ] as const)("sends exact %s read boundary", async (operation, path) => {
    const { client, fetch } = clientAndFetch();

    await client[operation]();

    assertRequest(fetch, { path, method: "GET", mutation: false });
  });

  it("sends exact session-read boundary", async () => {
    const { client, fetch } = clientAndFetch();

    await client.session(session.session_id);

    assertRequest(fetch, {
      path: `/api/v1/sessions/${session.session_id}`,
      method: "GET",
      mutation: false,
    });
  });

  it("sends exact turn-list boundary", async () => {
    const { client, fetch } = clientAndFetch();

    await client.turns(session.session_id);

    assertRequest(fetch, {
      path: `/api/v1/sessions/${session.session_id}/turns`,
      method: "GET",
      mutation: false,
    });
  });

  it("sends exact create-session mutation", async () => {
    const { client, fetch } = clientAndFetch();

    await client.createSession("30_days");

    assertRequest(fetch, {
      path: "/api/v1/sessions",
      method: "POST",
      body: {
        schema_version: "1",
        retention_policy: "30_days",
        connection_context_id: null,
      },
      mutation: true,
    });
  });

  it("sends exact create-turn mutation", async () => {
    const { client, fetch } = clientAndFetch();

    await client.createTurn(session, "Analyze the login flow.");

    assertRequest(fetch, {
      path: `/api/v1/sessions/${session.session_id}/turns`,
      method: "POST",
      body: {
        schema_version: "1",
        session_id: session.session_id,
        expected_revision: 3,
        user_message: "Analyze the login flow.",
      },
      mutation: true,
    });
  });

  it("sends exact close-session mutation", async () => {
    const { client, fetch } = clientAndFetch();

    await client.closeSession(session);

    assertRequest(fetch, {
      path: `/api/v1/sessions/${session.session_id}/close`,
      method: "POST",
      body: {
        schema_version: "1",
        session_id: session.session_id,
        expected_revision: 3,
      },
      mutation: true,
    });
  });

  it("sends exact delete-session mutation without a body", async () => {
    const { client, fetch } = clientAndFetch();

    await client.deleteSession(session.session_id);

    assertRequest(fetch, {
      path: `/api/v1/sessions/${session.session_id}`,
      method: "DELETE",
      mutation: true,
    });
  });
});
