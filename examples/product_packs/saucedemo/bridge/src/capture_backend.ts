import type { BridgeRequestV1, BridgeResponseV1 } from "./protocol.js";

export interface ProductCaptureBackend {
  capture(request: BridgeRequestV1): Promise<BridgeResponseV1>;
}

export class UnimplementedCaptureBackend implements ProductCaptureBackend {
  async capture(request: BridgeRequestV1): Promise<BridgeResponseV1> {
    return {
      protocol_version: "1",
      request_id: request.request_id,
      workflow_id: request.workflow_id,
      product_id: request.product_id,
      pack_id: request.pack_id,
      tool_id: request.tool_id,
      operation: request.operation,
      status: "failed",
      completed_at: request.requested_at,
      evidence: null,
      failure_code: "protocol_failure",
    };
  }
}
