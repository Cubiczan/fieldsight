"use client";

import { formatDecisionAid } from "@/lib/jev/format";
import type { FieldSightAid } from "@/lib/jev/types";

export function DecisionAid({ aid }: { aid: FieldSightAid }) {
  const copy = formatDecisionAid(aid);
  const source =
    aid.source === "jev" && aid.model ? `Jev · ${aid.model}` : aid.source === "jev" ? "Jev" : "Local heuristic";
  return (
    <section aria-label="Decision aid" className="rounded-xl bg-card px-4 py-4 ring-1 ring-foreground/10 sm:px-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">{copy.label}</p>
          <p className="mt-1 text-xs text-muted-foreground">{source}</p>
        </div>
        <p className="font-[family-name:var(--font-display)] text-4xl leading-none font-semibold">{copy.suggestion}</p>
      </div>
      <p className="mt-3 text-sm leading-6">{copy.confidenceText}</p>
      <p className="mt-1 text-sm text-muted-foreground">{copy.flags}</p>
      <p className="mt-2 text-sm leading-6">{copy.authorityText}</p>
    </section>
  );
}
