export type Trade = "electrical" | "hvac" | "plumbing";

export type Sample = {
  id: string;
  title: string;
  scene: string;
  trade: Trade;
  file: string;
};

export const TRADES: { id: Trade; label: string }[] = [
  { id: "electrical", label: "Electrical" },
  { id: "hvac", label: "HVAC" },
  { id: "plumbing", label: "Plumbing" },
];

export const SAMPLES: Sample[] = [
  {
    id: "clear-ready",
    title: "Vest on, panel latched",
    scene: "Hi-vis vest, closed cover, warning label on the wall.",
    trade: "electrical",
    file: "clear-ready.png",
  },
  {
    id: "hold-ppe",
    title: "No hi-vis vest",
    scene: "Latched panel and label, tech in a blue work shirt.",
    trade: "hvac",
    file: "hold-ppe.png",
  },
  {
    id: "escalate-open",
    title: "Open load center",
    scene: "Cover off, breakers exposed, no vest, no warning label.",
    trade: "electrical",
    file: "escalate-open.png",
  },
  {
    id: "escalate-vest-open",
    title: "Vest on, cover off",
    scene: "Hi-vis is on. The panel is open and the label is missing.",
    trade: "plumbing",
    file: "escalate-vest-open.png",
  },
];
