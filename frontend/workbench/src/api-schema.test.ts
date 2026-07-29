import { describe, expect, it } from "vitest";

import schema from "./api-v1.contract.json";

describe("versioned API fixture", () => {
  it("pins every outer Web API contract and field", () => {
    expect(schema.contracts).toEqual({
      HealthResponse: ["schema_version", "api_version", "readiness"],
      WorkflowCatalogResponse: ["schema_version", "workflows"],
      CreateSessionRequest: [
        "schema_version",
        "retention_policy",
        "connection_context_id",
      ],
      CloseSessionRequest: [
        "schema_version",
        "session_id",
        "expected_revision",
      ],
      CreateTurnRequest: [
        "schema_version",
        "session_id",
        "expected_revision",
        "user_message",
      ],
      SessionResponse: ["schema_version", "session"],
      SessionListResponse: ["schema_version", "sessions"],
      TurnResponse: ["schema_version", "turn"],
      TurnListResponse: ["schema_version", "turns"],
      TurnMutationResponse: ["schema_version", "session", "turn"],
      DeleteSessionResponse: ["schema_version", "deleted"],
    });
  });

  it("pins every selected nested contract and enum value", () => {
    expect(schema.schema_version).toBe("1");
    expect(schema.selected_domain_fields).toEqual({
      ConversationSession: [
        "schema_version",
        "session_id",
        "revision",
        "status",
        "retention_policy",
        "connection_context_id",
        "turn_ids",
        "created_at",
        "updated_at",
        "expires_at",
      ],
      ConversationTurn: [
        "schema_version",
        "turn_id",
        "session_id",
        "sequence_number",
        "status",
        "user_message",
        "assistant_response",
        "error_code",
        "error_message",
        "created_at",
        "completed_at",
      ],
      WorkflowDefinition: [
        "schema_version",
        "workflow_id",
        "workflow_version",
        "display_name",
        "description",
      ],
    });
    expect(schema.enum_values).toEqual({
      ConversationRetentionPolicy: [
        "session_only",
        "7_days",
        "30_days",
        "90_days",
      ],
      ConversationSessionStatus: ["active", "closed"],
      ConversationTurnStatus: ["pending", "completed", "failed"],
    });
  });

  it("pins the complete APIClient operation method/path inventory", () => {
    expect(schema.operations).toEqual({
      health: { method: "GET", path: "/api/v1/health" },
      workflows: { method: "GET", path: "/api/v1/workflows" },
      sessions: { method: "GET", path: "/api/v1/sessions" },
      session: {
        method: "GET",
        path: "/api/v1/sessions/{session_id}",
      },
      turns: {
        method: "GET",
        path: "/api/v1/sessions/{session_id}/turns",
      },
      createSession: { method: "POST", path: "/api/v1/sessions" },
      createTurn: {
        method: "POST",
        path: "/api/v1/sessions/{session_id}/turns",
      },
      closeSession: {
        method: "POST",
        path: "/api/v1/sessions/{session_id}/close",
      },
      deleteSession: {
        method: "DELETE",
        path: "/api/v1/sessions/{session_id}",
      },
    });
  });
});
