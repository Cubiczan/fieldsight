import type { Gate, JobsiteState, JevReading } from "./types";

/**
 * Local stand-in for the office policy in backend/app/agent.py.
 * Keep the branches aligned with backend/app/jev.py heuristic_decision.
 */
export function heuristicDecision(state: JobsiteState): {
  decision: Gate;
  open_panel: number;
  vest_missing: number;
  urgency: number;
} {
  const panel = state.panel_state;
  let decision: Gate;
  if (panel === "open") decision = "ESCALATE";
  else if (!state.vest_present || (panel === "closed" && !state.label_present)) decision = "HOLD";
  else decision = "CLEAR";

  const openPanel = panel === "open" ? 0.96 : panel === "closed" ? 0.04 : 0.02;
  const vestMissing = state.vest_present ? 0.04 : 0.96;
  const base = decision === "CLEAR" ? 0.1 : decision === "HOLD" ? 1.15 : 2.85;
  const openPriors = state.prior_tickets.filter((ticket) => ticket.status === "open").length;
  const urgency = Math.min(3, Math.round((base + openPriors * 0.25) * 100) / 100);
  return { decision, open_panel: openPanel, vest_missing: vestMissing, urgency };
}

export function readingFromHeuristic(state: JobsiteState): JevReading {
  const heuristic = heuristicDecision(state);
  return {
    source: "heuristic",
    model: null,
    decision: heuristic.decision,
    confidence: null,
    calibrated: false,
    open_panel: heuristic.open_panel,
    vest_missing: heuristic.vest_missing,
    urgency: heuristic.urgency,
    urgency_confidence: null,
  };
}
