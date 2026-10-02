export type Gate = "CLEAR" | "HOLD" | "ESCALATE";

export type PanelState = "open" | "closed" | "none";

export type PriorTicket = {
  id: string;
  status: string;
  priority?: string;
};

/** Structured jobsite state. Jev never receives the photo. */
export type JobsiteState = {
  trade: string;
  vest_present: boolean;
  vest_coverage: number;
  vest_threshold: number;
  panel_state: PanelState;
  panel_latched: boolean;
  edge_density: number | null;
  open_edge_threshold: number;
  label_present: boolean;
  prior_tickets: PriorTicket[];
  measurement_summary: string;
  measurements: {
    opencv_version: string;
    panel_candidates: number;
    label_regions: number;
  };
};

export type ChoiceQuestion = {
  type: "choice";
  instructions: string;
  criteria: Record<string, string>;
};

export type ScoreQuestion = {
  type: "score";
  instructions: string;
  criteria: string[];
};

export type NoulQuestion = {
  type: "noul";
  instructions: string;
  criteria?: { true: string; false: string };
};

export type Question = ChoiceQuestion | ScoreQuestion | NoulQuestion;

export type ChoiceAnswer = {
  type: "choice";
  choice: string;
  probabilities: Record<string, number>;
  confidence: number;
};

export type ScoreAnswer = {
  type: "score";
  score: number;
  legend: Record<string, string>;
  probabilities: Record<string, number>;
  confidence: number;
};

export type NoulAnswer = {
  type: "noul";
  noul: number;
};

export type Answer = ChoiceAnswer | ScoreAnswer | NoulAnswer;

export type SystemOneResponse = {
  model: string;
  answers: Record<string, Answer>;
  usage: { input_tokens: number; output_tokens: number };
};

export type JevReading = {
  source: "jev" | "heuristic";
  model: string | null;
  decision: Gate;
  confidence: number | null;
  calibrated: boolean;
  open_panel: number;
  vest_missing: number;
  urgency: number;
  urgency_confidence: number | null;
};

/** What the inspection API returns and the UI renders. */
export type FieldSightAid = JevReading & {
  authority: "policy" | "jev";
  applied_decision: Gate;
  policy_decision: Gate;
  agrees_with_policy: boolean;
  note: string;
};
