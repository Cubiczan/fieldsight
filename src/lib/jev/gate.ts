import type { FieldSightAid, Gate, JevReading, PanelState } from "./types";

/** Below this, a primary Jev choice escalates for a person to review. */
export const CONFIDENCE_MIN = 0.7;

export function applyGate(input: {
  policy: Gate;
  reading: JevReading;
  panelState: PanelState;
  primary: boolean;
}): { applied: Gate; authority: "policy" | "jev"; note: string } {
  const { policy, reading, panelState, primary } = input;
  if (!primary) {
    return {
      applied: policy,
      authority: "policy",
      note: "The office policy sets the gate. This result is a decision aid.",
    };
  }
  if (reading.source !== "jev") {
    return {
      applied: policy,
      authority: "policy",
      note: "Jev was not called, so the office policy stays the gate.",
    };
  }
  if (panelState === "open" && reading.decision !== "ESCALATE") {
    return {
      applied: "ESCALATE",
      authority: "policy",
      note: "The panel reads open, so the gate stays ESCALATE. This aid cannot clear exposed gear.",
    };
  }
  if (reading.confidence == null || reading.confidence < CONFIDENCE_MIN) {
    return {
      applied: "ESCALATE",
      authority: "jev",
      note: "Calibrated confidence is below 0.70, so the gate escalates for a person to review.",
    };
  }
  return {
    applied: reading.decision,
    authority: "jev",
    note: "JEV_PRIMARY is on and calibrated confidence is at least 0.70, so this aid sets the gate. It is not a determination that the equipment is safe to touch.",
  };
}

export function composeAid(
  policy: Gate,
  reading: JevReading,
  panelState: PanelState,
  primary: boolean,
): FieldSightAid {
  const gate = applyGate({ policy, reading, panelState, primary });
  return {
    ...reading,
    authority: gate.authority,
    applied_decision: gate.applied,
    policy_decision: policy,
    agrees_with_policy: reading.decision === policy,
    note: gate.note,
  };
}
