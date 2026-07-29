import { describe, expect, it } from "vitest";

import schema from "./api-v1.contract.json";

describe("versioned API fixture", () => {
  it("deliberately pins the Python Web v1 contract surface", () => {
    expect(schema.schema_version).toBe("1");
    expect(Object.keys(schema.contracts).sort()).toEqual(
      [
        "CloseSessionRequest",
        "CreateSessionRequest",
        "CreateTurnRequest",
        "DeleteSessionResponse",
        "HealthResponse",
        "SessionListResponse",
        "SessionResponse",
        "TurnListResponse",
        "TurnMutationResponse",
        "TurnResponse",
        "WorkflowCatalogResponse",
      ].sort(),
    );
  });
});
