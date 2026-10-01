"use client";

import { Badge } from "@/components/ui/badge";
import type { AgentStep } from "@/lib/inspection";
import { cn } from "@/lib/utils";

const phaseLabel: Record<AgentStep["phase"], string> = {
  perception: "Perceive",
  decision: "Decide",
  action: "Act",
};

export function AgentTrace({ steps, visibleCount }: { steps: AgentStep[]; visibleCount: number }) {
  return (
    <ol className="flex flex-col gap-2" aria-label="Agent steps">
      {steps.slice(0, visibleCount).map((step, index) => (
        <li
          key={`${step.tool}-${index}`}
          className={cn(
            "rounded-lg border px-3 py-2.5",
            step.status === "skipped" ? "border-dashed bg-muted/60 text-muted-foreground" : "bg-card",
          )}
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[11px] tracking-wide text-muted-foreground uppercase">
              {String(index + 1).padStart(2, "0")} {phaseLabel[step.phase]}
            </span>
            <span className="font-mono text-xs font-medium text-foreground">{step.tool}</span>
            <Badge variant={step.status === "executed" ? "default" : "outline"} className="ml-auto">
              {step.status}
            </Badge>
          </div>
          <p className="mt-1 text-sm leading-5">{step.detail}</p>
        </li>
      ))}
    </ol>
  );
}
