import type { FieldSightAid } from "./types";

export function formatDecisionAid(aid: FieldSightAid): {
  label: "Decision aid";
  suggestion: FieldSightAid["decision"];
  confidenceText: string;
  flags: string;
  authorityText: string;
} {
  const confidenceText =
    aid.calibrated && aid.confidence != null
      ? `Calibrated confidence ${Math.round(aid.confidence * 100)}%. This is a probability, not a certainty.`
      : "Local rules filled in because Jev was not called. This is not a calibrated model score.";
  const flags = aid.calibrated
    ? `Open panel ${Math.round(aid.open_panel * 100)}% yes · Vest missing ${Math.round(aid.vest_missing * 100)}% yes · Urgency ${aid.urgency.toFixed(1)} of 3`
    : `Open panel: ${aid.open_panel >= 0.5 ? "yes" : "no"} · Vest missing: ${aid.vest_missing >= 0.5 ? "yes" : "no"} · Urgency ${aid.urgency.toFixed(1)} of 3`;
  return {
    label: "Decision aid",
    suggestion: aid.decision,
    confidenceText,
    flags,
    authorityText: aid.note,
  };
}
