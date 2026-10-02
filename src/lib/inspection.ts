import type { FieldSightAid } from "@/lib/jev/types";
import type { Trade } from "@/lib/samples";

export type AgentStep = {
  phase: "perception" | "decision" | "action";
  tool: string;
  status: "executed" | "skipped";
  title: string;
  detail: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
};

export type Inspection = {
  overlay_jpeg_base64: string;
  findings: {
    image: { width: number; height: number };
    opencv: { version: string; stages: string[] };
    ppe_vest: { coverage: number; box: number[] | null; contour_count: number };
    electrical_panel: {
      candidates: { kind: string; box: number[]; area_ratio: number; edge_density: number }[];
    };
    warning_label: { regions: { color: string; box: number[]; area_ratio: number }[] };
  };
  agent: {
    inspection_id: string;
    decision: "CLEAR" | "HOLD" | "ESCALATE";
    trade: Trade;
    image_uri: string;
    storage: string;
    interpretation: {
      vest_present: boolean;
      vest_coverage: number;
      vest_threshold: number;
      panel_state: "open" | "closed" | "none";
      edge_density: number | null;
      open_edge_threshold: number;
      label_present: boolean;
    };
    steps: AgentStep[];
    sms: { to: string; body: string };
    clearance_note: string;
    note_source: string;
    ticket: { id: string; priority: string; title: string; summary: string; status: string } | null;
    jev: FieldSightAid;
  };
};

export function errorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}
