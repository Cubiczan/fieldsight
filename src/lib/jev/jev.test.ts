import assert from "node:assert/strict";
import test from "node:test";

import { decideJobsite, postSystemOne, resolveApiKey } from "./client";
import { heuristicDecision } from "./fallback";
import { buildRequest, jobsiteQuestions, readingFromResponse } from "./fieldsight";
import { formatDecisionAid } from "./format";
import { applyGate, composeAid } from "./gate";
import { JevParseError, parseSystemOne } from "./parse";
import { choice, noul, score } from "./questions";
import type { FieldSightAid, JobsiteState, JevReading, SystemOneResponse } from "./types";

function state(overrides: Partial<JobsiteState> = {}): JobsiteState {
  return {
    trade: "electrical",
    vest_present: true,
    vest_coverage: 0.068,
    vest_threshold: 0.04,
    panel_state: "closed",
    panel_latched: true,
    edge_density: 0.015,
    open_edge_threshold: 0.08,
    label_present: true,
    prior_tickets: [],
    measurement_summary: "electrical call. Hi-vis present. Panel closed.",
    measurements: { opencv_version: "5.0.0", panel_candidates: 1, label_regions: 1 },
    ...overrides,
  };
}

function response(overrides: Partial<SystemOneResponse["answers"]> = {}): SystemOneResponse {
  return {
    model: "jev-1.13.0",
    answers: {
      decision: {
        type: "choice",
        choice: "HOLD",
        probabilities: { CLEAR: 0.1, HOLD: 0.84, ESCALATE: 0.06 },
        confidence: 0.81,
      },
      open_panel: { type: "noul", noul: 0.07 },
      vest_missing: { type: "noul", noul: 0.9 },
      urgency: {
        type: "score",
        score: 1.2,
        legend: { "0": "Routine", "1": "Correctable", "2": "Urgent", "3": "Stop work" },
        probabilities: { "0": 0.05, "1": 0.75, "2": 0.15, "3": 0.05 },
        confidence: 0.7,
      },
      ...overrides,
    },
    usage: { input_tokens: 280, output_tokens: 0 },
  };
}

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), { status, headers });
}

test("choice, score, and noul build the System One question shapes", () => {
  const picked = choice("Which team?", { billing: "Payments", technical: "Bugs" });
  assert.equal(picked.type, "choice");
  assert.deepEqual(Object.keys(picked.criteria), ["billing", "technical"]);
  const rated = score("How urgent?", ["Low", "High"]);
  assert.deepEqual(rated.criteria, ["Low", "High"]);
  const flag = noul("Is it open?", { true: "Cover off", false: "Latched" });
  assert.equal(flag.criteria?.true, "Cover off");
  const bare = noul("Is it urgent?");
  assert.equal("criteria" in bare, false);
  assert.throws(() => choice("Only one", { only: "one" }), /2 and 255/);
  assert.throws(() => score("One level", ["Only"]), /2 and 10/);
});

test("jobsite questions ask for the gate, two flags, and urgency", () => {
  const questions = jobsiteQuestions();
  assert.equal(questions.decision.type, "choice");
  assert.deepEqual(Object.keys(questions.decision.criteria), ["CLEAR", "HOLD", "ESCALATE"]);
  assert.equal(questions.open_panel.type, "noul");
  assert.equal(questions.vest_missing.type, "noul");
  assert.equal(questions.urgency.type, "score");
  assert.equal(questions.urgency.criteria.length, 4);
  const request = buildRequest(state(), "jev-1.13.0");
  assert.equal(request.model, "jev-1.13.0");
  assert.equal("decision" in request.state, false);
});

test("parseSystemOne accepts a mixed Choice, Score, and Noul response", () => {
  const parsed = parseSystemOne(response());
  assert.equal(parsed.model, "jev-1.13.0");
  assert.equal(parsed.answers.decision.type, "choice");
  const reading = readingFromResponse(parsed);
  assert.equal(reading.source, "jev");
  assert.equal(reading.calibrated, true);
  assert.equal(reading.decision, "HOLD");
  assert.equal(reading.confidence, 0.81);
  assert.equal(reading.open_panel, 0.07);
  assert.equal(reading.vest_missing, 0.9);
  assert.equal(reading.urgency, 1.2);
  assert.equal(reading.urgency_confidence, 0.7);
});

test("parseSystemOne rejects malformed answers", () => {
  assert.throws(() => parseSystemOne(null), JevParseError);
  assert.throws(() => parseSystemOne({ model: "jev-1.13.0", answers: {}, usage: { input_tokens: 1, output_tokens: 0 } }), /empty/);
  const badChoice = response();
  badChoice.answers.decision = {
    type: "choice",
    choice: "HOLD",
    probabilities: { CLEAR: 0.2, HOLD: 0.2, ESCALATE: 0.2 },
    confidence: 0.4,
  };
  assert.throws(() => parseSystemOne(badChoice), /sum to 1/);
  const badNoul = response();
  badNoul.answers.open_panel = { type: "noul", noul: 1.4 };
  assert.throws(() => parseSystemOne(badNoul), /noul/);
  const missing = response();
  delete missing.answers.urgency;
  assert.throws(() => readingFromResponse(parseSystemOne(missing)), /urgency/);
  const outside = response();
  if (outside.answers.decision.type === "choice") {
    outside.answers.decision.choice = "WAIVE";
    outside.answers.decision.probabilities = { WAIVE: 1 };
  }
  assert.throws(() => readingFromResponse(parseSystemOne(outside)), /CLEAR, HOLD, or ESCALATE/);
});

test("fallback heuristics follow vest, panel, and label", () => {
  assert.equal(heuristicDecision(state()).decision, "CLEAR");
  assert.equal(heuristicDecision(state()).open_panel, 0.04);
  assert.equal(heuristicDecision(state()).vest_missing, 0.04);

  const hold = heuristicDecision(state({ vest_present: false, vest_coverage: 0 }));
  assert.equal(hold.decision, "HOLD");
  assert.equal(hold.vest_missing, 0.96);
  assert.ok(hold.urgency > 0.5 && hold.urgency < 2);

  const unlabeled = heuristicDecision(state({ label_present: false }));
  assert.equal(unlabeled.decision, "HOLD");

  const open = heuristicDecision(
    state({
      panel_state: "open",
      panel_latched: false,
      edge_density: 0.14,
      vest_present: false,
      vest_coverage: 0,
      label_present: false,
    }),
  );
  assert.equal(open.decision, "ESCALATE");
  assert.equal(open.open_panel, 0.96);
  assert.equal(open.vest_missing, 0.96);
  assert.ok(open.urgency > 2.5);

  const vestOpen = heuristicDecision(
    state({ panel_state: "open", panel_latched: false, label_present: false }),
  );
  assert.equal(vestOpen.decision, "ESCALATE");
  assert.equal(vestOpen.vest_missing, 0.04);

  const noPanel = heuristicDecision(
    state({ panel_state: "none", panel_latched: false, edge_density: null, label_present: false }),
  );
  assert.equal(noPanel.decision, "CLEAR");
  assert.equal(noPanel.open_panel, 0.02);

  const withTicket = heuristicDecision(state({ prior_tickets: [{ id: "FS-1", status: "open" }] }));
  assert.equal(withTicket.decision, "CLEAR");
  assert.equal(withTicket.urgency, 0.35);
});

test("applyGate keeps policy unless Jev is primary and confident", () => {
  const hold = readingFromResponse(parseSystemOne(response()));
  const dual = applyGate({ policy: "CLEAR", reading: hold, panelState: "closed", primary: false });
  assert.equal(dual.applied, "CLEAR");
  assert.equal(dual.authority, "policy");

  const primary = applyGate({ policy: "CLEAR", reading: hold, panelState: "closed", primary: true });
  assert.equal(primary.applied, "HOLD");
  assert.equal(primary.authority, "jev");
  assert.match(primary.note, /not a determination/);

  const unsure: JevReading = { ...hold, confidence: 0.42 };
  const escalated = applyGate({ policy: "CLEAR", reading: unsure, panelState: "closed", primary: true });
  assert.equal(escalated.applied, "ESCALATE");
  assert.match(escalated.note, /below 0.70/);

  const clearOpen: JevReading = { ...hold, decision: "CLEAR", confidence: 0.99 };
  const floor = applyGate({ policy: "ESCALATE", reading: clearOpen, panelState: "open", primary: true });
  assert.equal(floor.applied, "ESCALATE");
  assert.equal(floor.authority, "policy");
  assert.match(floor.note, /cannot clear exposed gear/);

  const offline = applyGate({
    policy: "HOLD",
    reading: { ...hold, source: "heuristic", calibrated: false, confidence: null, model: null },
    panelState: "closed",
    primary: true,
  });
  assert.equal(offline.applied, "HOLD");
  assert.equal(offline.authority, "policy");
});

test("formatDecisionAid labels the result and does not claim certainty", () => {
  const aid: FieldSightAid = composeAid("CLEAR", readingFromResponse(parseSystemOne(response())), "closed", false);
  const copy = formatDecisionAid(aid);
  assert.equal(copy.label, "Decision aid");
  assert.equal(copy.suggestion, "HOLD");
  assert.match(copy.confidenceText, /Calibrated confidence 81%/);
  assert.match(copy.confidenceText, /not a certainty/);
  assert.doesNotMatch(copy.confidenceText, /guaranteed|definitely safe|100% sure/);
  assert.match(copy.flags, /Open panel 7% yes/);
  assert.match(copy.flags, /Vest missing 90% yes/);

  const local = formatDecisionAid(
    composeAid("CLEAR", { ...aid, source: "heuristic", calibrated: false, confidence: null, model: null }, "closed", false),
  );
  assert.match(local.confidenceText, /not a calibrated model score/);
  assert.match(local.flags, /Open panel: no/);
});

test("resolveApiKey accepts either env name", () => {
  assert.equal(resolveApiKey({ JEV_API_KEY: " jev ", TYPESAFE_API_KEY: "other" }), "jev");
  assert.equal(resolveApiKey({ TYPESAFE_API_KEY: "safe" }), "safe");
  assert.equal(resolveApiKey({}), "");
});

test("decideJobsite uses the heuristic when no key is configured", async () => {
  let called = false;
  const fetchImpl = (async () => {
    called = true;
    throw new Error("network");
  }) as typeof fetch;
  const reading = await decideJobsite(state(), { apiKey: "", fetchImpl });
  assert.equal(called, false);
  assert.equal(reading.source, "heuristic");
  assert.equal(reading.calibrated, false);
  assert.equal(reading.decision, "CLEAR");
  assert.equal(reading.confidence, null);
});

test("decideJobsite parses a live response and falls back on failure", async () => {
  const seen: { body?: unknown; auth?: string } = {};
  const ok = (async (url: string, init?: RequestInit) => {
    seen.auth = new Headers(init?.headers).get("Authorization") ?? "";
    seen.body = JSON.parse(String(init?.body));
    assert.equal(url, "https://thejevai.com/v1/systemone");
    return jsonResponse(200, response());
  }) as typeof fetch;
  const reading = await decideJobsite(state({ vest_present: false }), {
    apiKey: "secret",
    fetchImpl: ok,
    env: {},
  });
  assert.equal(seen.auth, "Bearer secret");
  const body = seen.body as { questions: { decision: { type: string } }; state: { vest_present: boolean } };
  assert.equal(body.questions.decision.type, "choice");
  assert.equal(body.state.vest_present, false);
  assert.equal(reading.source, "jev");
  assert.equal(reading.decision, "HOLD");
  assert.equal(reading.confidence, 0.81);

  const failed = (async () => jsonResponse(500, { detail: "nope" })) as typeof fetch;
  const fallback = await decideJobsite(state({ vest_present: false, vest_coverage: 0 }), {
    apiKey: "secret",
    fetchImpl: failed,
  });
  assert.equal(fallback.source, "heuristic");
  assert.equal(fallback.decision, "HOLD");
  assert.equal(fallback.calibrated, false);
});

test("postSystemOne retries once on 429", async () => {
  let calls = 0;
  const fetchImpl = (async () => {
    calls += 1;
    if (calls === 1) return jsonResponse(429, { detail: "slow" }, { "retry-after-ms": "0" });
    return jsonResponse(200, response());
  }) as typeof fetch;
  const raw = await postSystemOne(buildRequest(state()), {
    apiKey: "secret",
    url: "https://thejevai.com/v1/systemone",
    fetchImpl,
    timeoutMs: 1000,
  });
  assert.equal(calls, 2);
  assert.equal(parseSystemOne(raw).model, "jev-1.13.0");
});
