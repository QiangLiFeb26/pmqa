export const BRIDGE_PROTOCOL_VERSION = "1" as const;

export type BridgeOperation = "exploration_capture";
export type BridgeStatus = "succeeded" | "failed";
export type BridgeFailureCode =
  | "exploration_failed"
  | "action_plan_rejected"
  | "protocol_failure";

export interface BridgeRequestV1 {
  protocol_version: "1";
  request_id: string;
  workflow_id: string;
  product_id: string;
  pack_id: string;
  tool_id: string;
  operation: "exploration_capture";
  requested_at: string;
  action_plan: string[];
}

export interface ExplorationSourceV1 {
  source_type: string;
  tool_id: string;
  capture_id: string;
}

export interface ObservedPageV1 {
  page_id: string;
  url: string;
  title: string;
  structural_fingerprint: string;
}

export interface ObservedAttributeV1 {
  name: string;
  value: string;
}

export interface ObservedElementV1 {
  element_id: string;
  page_id: string;
  role: string;
  accessible_name: string;
  visible_text: string | null;
  attributes: ObservedAttributeV1[];
}

export interface LocatorCandidateObservationV1 {
  locator_candidate_id: string;
  element_id: string;
  strategy: string;
  value: string;
  priority: number;
}

export interface InteractionObservationV1 {
  interaction_id: string;
  source_page_id: string;
  target_element_id: string;
  action: string;
  outcome_type: string;
  outcome_value: string;
}

export interface ExplorationEvidenceV1 {
  schema_version: string;
  evidence_id: string;
  workflow_id: string;
  product_id: string;
  source: ExplorationSourceV1;
  captured_at: string;
  pages: ObservedPageV1[];
  elements: ObservedElementV1[];
  locator_candidates: LocatorCandidateObservationV1[];
  interactions: InteractionObservationV1[];
}

export interface BridgeResponseV1 {
  protocol_version: "1";
  request_id: string;
  workflow_id: string;
  product_id: string;
  pack_id: string;
  tool_id: string;
  operation: "exploration_capture";
  status: BridgeStatus;
  completed_at: string;
  evidence: ExplorationEvidenceV1 | null;
  failure_code: BridgeFailureCode | null;
}
