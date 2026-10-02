import type { Answer, ChoiceAnswer, NoulAnswer, ScoreAnswer, SystemOneResponse } from "./types";

const SUM_TOLERANCE = 0.05;

export class JevParseError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "JevParseError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isProbability(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1;
}

function readProbabilities(value: unknown): Record<string, number> {
  if (!isRecord(value)) throw new JevParseError("probabilities must be an object");
  const entries = Object.entries(value);
  if (entries.length === 0) throw new JevParseError("probabilities must not be empty");
  const out: Record<string, number> = {};
  for (const [key, item] of entries) {
    if (!isProbability(item)) throw new JevParseError(`probability for ${key} is invalid`);
    out[key] = item;
  }
  const total = Object.values(out).reduce((sum, item) => sum + item, 0);
  if (Math.abs(total - 1) > SUM_TOLERANCE) {
    throw new JevParseError("probabilities must sum to 1");
  }
  return out;
}

function readChoice(value: Record<string, unknown>): ChoiceAnswer {
  if (typeof value.choice !== "string" || value.choice.length === 0) {
    throw new JevParseError("choice answer is missing choice");
  }
  if (!isProbability(value.confidence)) throw new JevParseError("choice confidence is invalid");
  const probabilities = readProbabilities(value.probabilities);
  if (!(value.choice in probabilities)) {
    throw new JevParseError("choice is missing from probabilities");
  }
  return { type: "choice", choice: value.choice, probabilities, confidence: value.confidence };
}

function readScore(value: Record<string, unknown>): ScoreAnswer {
  if (typeof value.score !== "number" || !Number.isFinite(value.score)) {
    throw new JevParseError("score answer is missing score");
  }
  if (!isProbability(value.confidence)) throw new JevParseError("score confidence is invalid");
  if (!isRecord(value.legend)) throw new JevParseError("score legend must be an object");
  const legend: Record<string, string> = {};
  for (const [key, item] of Object.entries(value.legend)) {
    if (typeof item !== "string") throw new JevParseError(`legend level ${key} must be a string`);
    legend[key] = item;
  }
  const probabilities = readProbabilities(value.probabilities);
  for (const key of Object.keys(probabilities)) {
    if (!(key in legend)) throw new JevParseError(`score level ${key} is missing from the legend`);
  }
  return {
    type: "score",
    score: value.score,
    legend,
    probabilities,
    confidence: value.confidence,
  };
}

function readNoul(value: Record<string, unknown>): NoulAnswer {
  if (!isProbability(value.noul)) throw new JevParseError("noul must be between 0 and 1");
  return { type: "noul", noul: value.noul };
}

function readAnswer(value: unknown): Answer {
  if (!isRecord(value)) throw new JevParseError("answer must be an object");
  if (value.type === "choice") return readChoice(value);
  if (value.type === "score") return readScore(value);
  if (value.type === "noul") return readNoul(value);
  throw new JevParseError("answer type is not choice, score, or noul");
}

export function parseSystemOne(raw: unknown): SystemOneResponse {
  if (!isRecord(raw)) throw new JevParseError("response must be an object");
  if (typeof raw.model !== "string" || raw.model.length === 0) {
    throw new JevParseError("response is missing model");
  }
  if (!isRecord(raw.answers)) throw new JevParseError("response is missing answers");
  const keys = Object.keys(raw.answers);
  if (keys.length === 0) throw new JevParseError("answers must not be empty");
  const answers: Record<string, Answer> = {};
  for (const key of keys) answers[key] = readAnswer(raw.answers[key]);
  if (!isRecord(raw.usage)) throw new JevParseError("response is missing usage");
  const input = raw.usage.input_tokens;
  const output = raw.usage.output_tokens;
  if (typeof input !== "number" || !Number.isInteger(input) || input < 0) {
    throw new JevParseError("usage.input_tokens is invalid");
  }
  if (typeof output !== "number" || !Number.isInteger(output) || output < 0) {
    throw new JevParseError("usage.output_tokens is invalid");
  }
  return { model: raw.model, answers, usage: { input_tokens: input, output_tokens: output } };
}
