"use client";

import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { AgentTrace } from "@/components/agent-trace";
import { errorMessage, type Inspection } from "@/lib/inspection";
import { SAMPLES, TRADES, type Sample, type Trade } from "@/lib/samples";
import { cn } from "@/lib/utils";

type Source =
  | { type: "sample"; id: string }
  | { type: "file"; file: File; previewUrl: string };

const decisionStyle = {
  CLEAR: "bg-[#1f7a4d]",
  HOLD: "bg-[#8a5a08]",
  ESCALATE: "bg-[#b42318]",
} as const;

const decisionLine = {
  CLEAR: "Crew can keep working this task.",
  HOLD: "Fix the gap and shoot the panel again.",
  ESCALATE: "Stop. Office gets an urgent ticket.",
} as const;

export function Inspector() {
  const [trade, setTrade] = useState<Trade>("electrical");
  const [samples, setSamples] = useState<Sample[]>(SAMPLES);
  const [opencv, setOpencv] = useState<string | null>(null);
  const [serviceError, setServiceError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Inspection | null>(null);
  const [activeSample, setActiveSample] = useState<string | null>(null);
  const [visibleSteps, setVisibleSteps] = useState(0);
  const [copied, setCopied] = useState(false);
  const [fromUpload, setFromUpload] = useState(false);
  const source = useRef<Source | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [healthResponse, sampleResponse] = await Promise.all([
          fetch("/api/vision/health"),
          fetch("/api/vision/v1/samples"),
        ]);
        if (!healthResponse.ok || !sampleResponse.ok) {
          throw new Error("Inspection service did not answer.");
        }
        const health = (await healthResponse.json()) as { opencv?: string };
        const listed = (await sampleResponse.json()) as {
          samples: { id: string; title: string; scene: string; trade: Trade; image_url: string }[];
        };
        if (cancelled) return;
        setOpencv(health.opencv ?? null);
        setSamples(
          listed.samples.map((sample) => ({
            id: sample.id,
            title: sample.title,
            scene: sample.scene,
            trade: sample.trade,
            file: sample.image_url.split("/").pop() ?? `${sample.id}.png`,
          })),
        );
        setServiceError(null);
      } catch {
        if (!cancelled) {
          setServiceError("The inspection service is not running. Start it with scripts/dev.sh, then reload.");
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!result) return;
    const stepCount = result.agent.steps.length;
    const timer = window.setInterval(() => {
      setVisibleSteps((count) => {
        if (count >= stepCount) {
          window.clearInterval(timer);
          return count;
        }
        return count + 1;
      });
    }, 650);
    return () => window.clearInterval(timer);
  }, [result]);

  useEffect(() => {
    return () => {
      if (source.current?.type === "file") URL.revokeObjectURL(source.current.previewUrl);
    };
  }, []);

  async function inspect(nextTrade: Trade, nextSource: Source) {
    setLoading(true);
    setError(null);
    setCopied(false);
    setResult(null);
    setVisibleSteps(0);
    try {
      let response: Response;
      if (nextSource.type === "sample") {
        setActiveSample(nextSource.id);
        setFromUpload(false);
        response = await fetch(
          `/api/vision/v1/inspections/samples/${nextSource.id}?trade=${nextTrade}`,
          { method: "POST" },
        );
      } else {
        setActiveSample(null);
        setFromUpload(true);
        const form = new FormData();
        form.set("file", nextSource.file);
        form.set("trade", nextTrade);
        response = await fetch("/api/vision/v1/inspections", { method: "POST", body: form });
      }
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(errorMessage(body, "Inspection failed."));
      }
      setVisibleSteps(1);
      setResult(body as Inspection);
      requestAnimationFrame(() => {
        resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Inspection failed.");
    } finally {
      setLoading(false);
    }
  }

  function chooseSample(sample: Sample) {
    const next = { type: "sample", id: sample.id } as const;
    source.current = next;
    setTrade(sample.trade);
    void inspect(sample.trade, next);
  }

  function chooseFile(file: File) {
    if (source.current?.type === "file") URL.revokeObjectURL(source.current.previewUrl);
    const next = { type: "file", file, previewUrl: URL.createObjectURL(file) } as const;
    source.current = next;
    void inspect(trade, next);
  }

  function changeTrade(nextTrade: Trade) {
    setTrade(nextTrade);
    if (source.current) void inspect(nextTrade, source.current);
  }

  const decision = result?.agent.decision;
  const policyVisible = result
    ? result.agent.steps.slice(0, visibleSteps).some((step) => step.tool === "policy.check")
    : false;

  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-2xl">
          <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">
            HVAC · Electrical · Plumbing
          </p>
          <h1 className="mt-1 font-[family-name:var(--font-display)] text-4xl leading-none font-semibold tracking-tight sm:text-5xl">
            Check the photo before the crew touches the gear.
          </h1>
          <p className="mt-3 text-base leading-6 text-muted-foreground">
            Pick a jobsite fixture or upload a photo. OpenCV measures the vest, the panel interior,
            and the warning label. Those numbers pick the next tool: a clearance, a hold text, or an
            urgent office ticket.
          </p>
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Trade on this call</span>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Trade">
            {TRADES.map((item) => (
              <Button
                key={item.id}
                type="button"
                size="lg"
                variant={trade === item.id ? "default" : "outline"}
                className="h-11 px-4"
                aria-pressed={trade === item.id}
                onClick={() => changeTrade(item.id)}
              >
                {item.label}
              </Button>
            ))}
          </div>
          <p className="font-mono text-xs text-muted-foreground">
            {opencv ? `OpenCV ${opencv}` : "OpenCV …"}
            {serviceError ? "" : " · live analysis"}
          </p>
        </div>
      </section>

      {serviceError ? (
        <div role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm">
          {serviceError}
        </div>
      ) : null}

      <section aria-label="Jobsite photos">
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold">Jobsite fixtures</h2>
          <p className="text-sm text-muted-foreground">Synthetic scenes, drawn so the demo is repeatable.</p>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {samples.map((sample) => {
            const selected = activeSample === sample.id;
            return (
              <button
                key={sample.id}
                type="button"
                onClick={() => chooseSample(sample)}
                disabled={loading}
                className={cn(
                  "overflow-hidden rounded-xl bg-card text-left ring-1 ring-foreground/10 transition disabled:opacity-60",
                  selected ? "ring-2 ring-primary" : "hover:ring-foreground/25",
                )}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`/samples/${sample.file}`}
                  alt=""
                  className="aspect-[3/2] w-full object-cover"
                />
                <span className="block px-3 py-2.5">
                  <span className="block text-sm font-semibold">{sample.title}</span>
                  <span className="mt-1 block text-xs leading-4 text-muted-foreground">{sample.scene}</span>
                </span>
              </button>
            );
          })}
        </div>
      </section>

      <section
        className="rounded-xl border border-dashed border-foreground/20 bg-card px-4 py-5"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          const file = event.dataTransfer.files?.[0];
          if (file) chooseFile(file);
        }}
      >
        <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold">Or upload a jobsite photo</h2>
            <p className="mt-1 max-w-xl text-sm text-muted-foreground">
              JPEG, PNG, or WebP, up to 10 MB. Real rooms will not match the fixture colors exactly.
              Treat the result as a screen, then confirm it on site.
            </p>
          </div>
          <Button
            type="button"
            size="lg"
            className="h-11 px-4"
            disabled={loading}
            onClick={() => fileInput.current?.click()}
          >
            Choose photo
          </Button>
          <input
            ref={fileInput}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="sr-only"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) chooseFile(file);
              event.target.value = "";
            }}
          />
        </div>
      </section>

      {error ? (
        <div role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm">
          {error}
        </div>
      ) : null}

      {loading ? (
        <Card className="px-4 py-6" role="status">
          <p className="font-[family-name:var(--font-display)] text-2xl font-semibold">Reading the photo</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Orange vest mask, Canny edges inside the panel, yellow and red placard contours. Then the
            agent picks a tool.
          </p>
        </Card>
      ) : null}

      {result ? (
        <div ref={resultRef} className="flex flex-col gap-4">
          <section
            className={cn(
              "rounded-xl px-4 py-5 text-white sm:px-6",
              policyVisible && decision ? decisionStyle[decision] : "bg-foreground",
            )}
            aria-live="polite"
          >
            <p className="font-mono text-xs tracking-widest uppercase opacity-80">
              {result.agent.inspection_id} · {result.agent.trade}
            </p>
            <h2 className="mt-1 font-[family-name:var(--font-display)] text-5xl leading-none font-semibold">
              {policyVisible && decision ? decision : "Reading…"}
            </h2>
            <p className="mt-2 max-w-2xl text-sm sm:text-base">
              {policyVisible && decision
                ? decisionLine[decision]
                : "Measurements are in. The policy check has not spoken yet."}
            </p>
          </section>

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
            <div className="flex flex-col gap-3">
              <figure className="overflow-hidden rounded-xl bg-card ring-1 ring-foreground/10">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`data:image/jpeg;base64,${result.overlay_jpeg_base64}`}
                  alt="Photo with OpenCV boxes for the vest, panel, and warning label. A Canny edge thumbnail sits in the corner."
                  className="w-full"
                />
                <figcaption className="flex flex-wrap gap-2 px-3 py-2 text-xs text-muted-foreground">
                  <Legend swatch="bg-[#1f7a4d]" label="Hi-vis vest" />
                  <Legend swatch="bg-[#1d4e89]" label="Latched cover" />
                  <Legend swatch="bg-[#b42318]" label="Open interior" />
                  <Legend swatch="bg-[#e6b325]" label="Warning label" />
                  <span>Corner inset is the Canny edge map.</span>
                </figcaption>
              </figure>
              {fromUpload ? (
                <p className="text-xs text-muted-foreground">Uploaded file, not a fixture.</p>
              ) : null}
              <dl className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                <Metric
                  label="Hi-vis coverage"
                  value={`${(result.agent.interpretation.vest_coverage * 100).toFixed(1)}%`}
                  hint={`${result.agent.interpretation.vest_present ? "Over" : "Under"} ${(result.agent.interpretation.vest_threshold * 100).toFixed(0)}% torso threshold`}
                />
                <Metric
                  label="Panel edges"
                  value={
                    result.agent.interpretation.edge_density == null
                      ? "No panel"
                      : `${(result.agent.interpretation.edge_density * 100).toFixed(1)}%`
                  }
                  hint={
                    result.agent.interpretation.panel_state === "none"
                      ? "Interior measurement skipped"
                      : `${result.agent.interpretation.panel_state} · open at ${(result.agent.interpretation.open_edge_threshold * 100).toFixed(0)}%`
                  }
                />
                <Metric
                  label="Warning label"
                  value={result.agent.interpretation.label_present ? "In frame" : "Missing"}
                  hint={`${result.findings.warning_label.regions.length} yellow or red region${result.findings.warning_label.regions.length === 1 ? "" : "s"}`}
                />
              </dl>
            </div>

            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between gap-2">
                <h3 className="font-[family-name:var(--font-display)] text-2xl font-semibold">What the agent did</h3>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setVisibleSteps(result.agent.steps.length)}
                >
                  Show all
                </Button>
              </div>
              <AgentTrace steps={result.agent.steps} visibleCount={visibleSteps} />
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="px-4">
              <div className="flex items-center justify-between gap-2">
                <h3 className="font-[family-name:var(--font-display)] text-2xl font-semibold">Text to send</h3>
                <Badge variant="outline">{result.agent.sms.to}</Badge>
              </div>
              <p className="mt-3 text-sm leading-6">{result.agent.sms.body}</p>
              <Button
                type="button"
                variant="secondary"
                className="mt-4 h-10"
                onClick={() => {
                  void navigator.clipboard.writeText(result.agent.sms.body).then(() => {
                    setCopied(true);
                  });
                }}
              >
                {copied ? "Copied" : "Copy text"}
              </Button>
            </Card>
            <Card className="px-4">
              <div className="flex items-center justify-between gap-2">
                <h3 className="font-[family-name:var(--font-display)] text-2xl font-semibold">Clearance note</h3>
                <Badge variant="outline">{result.agent.note_source}</Badge>
              </div>
              <pre className="mt-3 font-mono text-xs leading-5 whitespace-pre-wrap">{result.agent.clearance_note}</pre>
              <p className="mt-3 text-xs text-muted-foreground">
                Stored at {result.agent.image_uri}
                {result.agent.storage === "local-mock"
                  ? " via the local S3 mock. Set FIELDSIGHT_S3_BUCKET and AWS credentials to write to S3."
                  : " in S3."}
              </p>
            </Card>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Legend({ swatch, label }: { swatch: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={cn("size-2.5 rounded-sm", swatch)} />
      {label}
    </span>
  );
}

function Metric({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-xl bg-card px-3 py-3 ring-1 ring-foreground/10">
      <dt className="text-xs tracking-wide text-muted-foreground uppercase">{label}</dt>
      <dd className="mt-1 font-[family-name:var(--font-display)] text-3xl leading-none font-semibold">{value}</dd>
      <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}
