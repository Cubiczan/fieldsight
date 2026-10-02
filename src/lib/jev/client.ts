import { readingFromHeuristic } from "./fallback";
import { buildRequest, DEFAULT_MODEL, DEFAULT_URL, readingFromResponse } from "./fieldsight";
import { parseSystemOne } from "./parse";
import type { JobsiteState, JevReading } from "./types";

export function resolveApiKey(env: Record<string, string | undefined>): string {
  return (env.JEV_API_KEY || env.TYPESAFE_API_KEY || "").trim();
}

function retryDelayMs(headers: Headers): number {
  const millis = headers.get("retry-after-ms");
  if (millis != null && millis !== "" && Number.isFinite(Number(millis))) {
    return Math.min(Math.max(0, Number(millis)), 1000);
  }
  const seconds = headers.get("retry-after");
  if (seconds != null && seconds !== "" && Number.isFinite(Number(seconds))) {
    return Math.min(Math.max(0, Number(seconds) * 1000), 1000);
  }
  return 200;
}

export async function postSystemOne(
  body: unknown,
  options: { apiKey: string; url: string; fetchImpl: typeof fetch; timeoutMs: number },
): Promise<unknown> {
  let delayMs = 0;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    if (attempt > 0) await new Promise((resolve) => setTimeout(resolve, delayMs));
    const response = await options.fetchImpl(options.url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${options.apiKey}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(options.timeoutMs),
    });
    if ((response.status === 429 || response.status === 529) && attempt === 0) {
      delayMs = retryDelayMs(response.headers);
      continue;
    }
    if (!response.ok) throw new Error(`Jev request failed: ${response.status}`);
    return response.json() as Promise<unknown>;
  }
  throw new Error("Jev request failed");
}

export async function decideJobsite(
  state: JobsiteState,
  options: {
    apiKey?: string;
    env?: Record<string, string | undefined>;
    model?: string;
    url?: string;
    fetchImpl?: typeof fetch;
    timeoutMs?: number;
  } = {},
): Promise<JevReading> {
  const env = options.env ?? process.env;
  const apiKey = (options.apiKey !== undefined ? options.apiKey : resolveApiKey(env)).trim();
  if (!apiKey) return readingFromHeuristic(state);
  const fetchImpl = options.fetchImpl ?? fetch;
  const url = options.url ?? env.JEV_API_URL ?? DEFAULT_URL;
  const model = options.model ?? env.JEV_MODEL ?? DEFAULT_MODEL;
  try {
    const raw = await postSystemOne(buildRequest(state, model), {
      apiKey,
      url,
      fetchImpl,
      timeoutMs: options.timeoutMs ?? 4000,
    });
    return readingFromResponse(parseSystemOne(raw));
  } catch {
    return readingFromHeuristic(state);
  }
}
