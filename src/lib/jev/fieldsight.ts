import { JevParseError } from "./parse";
import { choice, noul, score } from "./questions";
import type { Gate, JobsiteState, JevReading, SystemOneResponse } from "./types";

export const DEFAULT_MODEL = "jev-1.13.0";
export const DEFAULT_URL = "https://thejevai.com/v1/systemone";

const GATES: readonly Gate[] = ["CLEAR", "HOLD", "ESCALATE"];

export function jobsiteQuestions() {
  return {
    decision: choice(
      "Which gate should the crew follow from these measurements? This is a decision aid, not a determination that equipment is safe to touch.",
      {
        CLEAR:
          "Vest is present, the panel is latched or no panel is in frame, and a warning label is beside the panel when a panel is in frame.",
        HOLD:
          "No exposed live gear, but a correctable gap remains, such as a missing vest or a missing warning label. No urgent ticket.",
        ESCALATE:
          "The panel interior reads as open, or a person needs to stop work and open an urgent office ticket.",
      },
    ),
    open_panel: noul("Does the structured state say the electrical panel interior is open (cover off)?", {
      true: "panel_state is open",
      false: "panel_state is closed (latched) or none (no panel contour)",
    }),
    vest_missing: noul("Is a hi-vis vest missing from the photo?", {
      true: "vest_present is false or vest_coverage is below vest_threshold",
      false: "vest_present is true and coverage meets the torso threshold",
    }),
    urgency: score(
      "How urgent is a human follow-up, based only on these measurements and any prior tickets?",
      [
        "Routine: vest, cover, and label are in order",
        "Correctable: a gap the crew can fix on site",
        "Urgent: exposed gear or a missing guard that should stop work",
        "Stop work: open panel, treat as an immediate office escalation",
      ],
    ),
  };
}

export function buildRequest(state: JobsiteState, model = DEFAULT_MODEL) {
  return { model, state, questions: jobsiteQuestions() };
}

function isGate(value: string): value is Gate {
  return (GATES as readonly string[]).includes(value);
}

export function readingFromResponse(parsed: SystemOneResponse): JevReading {
  const decision = parsed.answers.decision;
  const openPanel = parsed.answers.open_panel;
  const vestMissing = parsed.answers.vest_missing;
  const urgency = parsed.answers.urgency;
  if (!decision || decision.type !== "choice" || !isGate(decision.choice)) {
    throw new JevParseError("decision choice must be CLEAR, HOLD, or ESCALATE");
  }
  if (!openPanel || openPanel.type !== "noul") throw new JevParseError("open_panel must be a noul");
  if (!vestMissing || vestMissing.type !== "noul") throw new JevParseError("vest_missing must be a noul");
  if (!urgency || urgency.type !== "score") throw new JevParseError("urgency must be a score");
  return {
    source: "jev",
    model: parsed.model,
    decision: decision.choice,
    confidence: decision.confidence,
    calibrated: true,
    open_panel: openPanel.noul,
    vest_missing: vestMissing.noul,
    urgency: urgency.score,
    urgency_confidence: urgency.confidence,
  };
}
