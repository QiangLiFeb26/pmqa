import type { RuntimeCredentials } from "./bootstrap";

export type RetentionPolicy =
  | "session_only"
  | "7_days"
  | "30_days"
  | "90_days";

export interface WorkflowDefinition {
  readonly schema_version: "1";
  readonly workflow_id: string;
  readonly workflow_version: string;
  readonly display_name: string;
  readonly description: string;
}

export interface ConversationSession {
  readonly schema_version: "1";
  readonly session_id: string;
  readonly revision: number;
  readonly status: "active" | "closed";
  readonly retention_policy: RetentionPolicy;
  readonly connection_context_id: string | null;
  readonly turn_ids: readonly string[];
  readonly created_at: string;
  readonly updated_at: string;
  readonly expires_at: string | null;
}

export interface ConversationTurn {
  readonly schema_version: "1";
  readonly turn_id: string;
  readonly session_id: string;
  readonly sequence_number: number;
  readonly status: "pending" | "completed" | "failed";
  readonly user_message: string;
  readonly assistant_response: string | null;
  readonly error_code: string | null;
  readonly error_message: string | null;
  readonly created_at: string;
  readonly completed_at: string | null;
}

interface APIErrorPayload {
  readonly schema_version: "1";
  readonly error: {
    readonly code: string;
    readonly message: string;
  };
}

export class APIError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, status: number) {
    super("PMQA request failed");
    this.name = "APIError";
    this.code = code;
    this.status = status;
  }
}

export class APIClient {
  readonly #credentials: RuntimeCredentials;

  constructor(credentials: RuntimeCredentials) {
    this.#credentials = credentials;
  }

  health(): Promise<{ readonly readiness: "ready" }> {
    return this.#request("/api/v1/health");
  }

  workflows(): Promise<{ readonly workflows: readonly WorkflowDefinition[] }> {
    return this.#request("/api/v1/workflows");
  }

  sessions(): Promise<{ readonly sessions: readonly ConversationSession[] }> {
    return this.#request("/api/v1/sessions");
  }

  session(
    sessionId: string,
  ): Promise<{ readonly session: ConversationSession }> {
    return this.#request(`/api/v1/sessions/${sessionId}`);
  }

  turns(
    sessionId: string,
  ): Promise<{ readonly turns: readonly ConversationTurn[] }> {
    return this.#request(`/api/v1/sessions/${sessionId}/turns`);
  }

  createSession(
    retentionPolicy: RetentionPolicy,
  ): Promise<{ readonly session: ConversationSession }> {
    return this.#request("/api/v1/sessions", {
      method: "POST",
      body: JSON.stringify({
        schema_version: "1",
        retention_policy: retentionPolicy,
        connection_context_id: null,
      }),
    });
  }

  createTurn(
    session: ConversationSession,
    userMessage: string,
  ): Promise<{
    readonly session: ConversationSession;
    readonly turn: ConversationTurn;
  }> {
    return this.#request(`/api/v1/sessions/${session.session_id}/turns`, {
      method: "POST",
      body: JSON.stringify({
        schema_version: "1",
        session_id: session.session_id,
        expected_revision: session.revision,
        user_message: userMessage,
      }),
    });
  }

  closeSession(
    session: ConversationSession,
  ): Promise<{ readonly session: ConversationSession }> {
    return this.#request(`/api/v1/sessions/${session.session_id}/close`, {
      method: "POST",
      body: JSON.stringify({
        schema_version: "1",
        session_id: session.session_id,
        expected_revision: session.revision,
      }),
    });
  }

  deleteSession(sessionId: string): Promise<{ readonly deleted: true }> {
    return this.#request(`/api/v1/sessions/${sessionId}`, {
      method: "DELETE",
    });
  }

  async #request<T>(
    path: string,
    init: RequestInit = {},
  ): Promise<T> {
    const mutation = init.method !== undefined && init.method !== "GET";
    const headers = new Headers({
      Authorization: `Bearer ${this.#credentials.sessionToken}`,
    });
    if (mutation) {
      headers.set("X-PMQA-CSRF-Token", this.#credentials.csrfToken);
      if (init.body !== undefined) {
        headers.set("Content-Type", "application/json");
      }
    }
    const response = await fetch(path, {
      ...init,
      headers,
      credentials: "omit",
      cache: "no-store",
      referrerPolicy: "no-referrer",
    });
    const payload: unknown = await response.json();
    if (!response.ok) {
      const error = payload as Partial<APIErrorPayload>;
      throw new APIError(
        typeof error.error?.code === "string"
          ? error.error.code
          : "internal_failed",
        response.status,
      );
    }
    return payload as T;
  }
}
