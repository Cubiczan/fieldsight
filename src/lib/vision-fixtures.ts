import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { Inspection } from "@/lib/inspection";
import { SAMPLES, type Trade } from "@/lib/samples";

const FIXTURE_DIR = join(process.cwd(), "src/lib/fixtures");

const TRADES: Trade[] = ["electrical", "hvac", "plumbing"];

export function healthPayload() {
  return { status: "ok", service: "fieldsight", opencv: "5.0.0" };
}

export function samplesPayload() {
  return {
    samples: SAMPLES.map((sample) => ({
      id: sample.id,
      title: sample.title,
      scene: sample.scene,
      trade: sample.trade,
      expected:
        sample.id === "clear-ready"
          ? "CLEAR"
          : sample.id === "hold-ppe"
            ? "HOLD"
            : "ESCALATE",
      image_url: `/samples/${sample.file}`,
    })),
  };
}

export function loadInspection(sampleId: string, trade: string): Inspection | null {
  const cleaned = trade.trim().toLowerCase();
  if (!TRADES.includes(cleaned as Trade)) return null;
  if (!SAMPLES.some((s) => s.id === sampleId)) return null;
  const path = join(FIXTURE_DIR, `${sampleId}__${cleaned}.json`);
  try {
    return JSON.parse(readFileSync(path, "utf8")) as Inspection;
  } catch {
    return null;
  }
}
