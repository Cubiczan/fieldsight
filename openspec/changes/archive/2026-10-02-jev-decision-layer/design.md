## Context

OpenCV in `backend/app/vision.py` returns measurements only. `backend/app/agent.py` maps vest coverage, panel edge density, and a nearby warning label to CLEAR, HOLD, or ESCALATE, then drafts a ticket and a text. Jev accepts text or JSON state and returns Choice, Score, and Noul answers with probabilities. It does not accept the photo.

## Goals / Non-Goals

**Goals:**

- One System One call per inspection with a CLEAR|HOLD|ESCALATE Choice, Noul flags for an open panel and a missing vest, and an urgency Score.
- Demos and `npm run build` work with no key, using the same branches as the office policy.
- The UI shows the aid and a calibrated confidence only when Jev actually answered.
- Dual-run compares both gates in the log and keeps the office policy unless `JEV_PRIMARY=1`.

**Non-Goals:**

- Replacing OpenCV, Bedrock phrasing, or the SMS and ticket templates.
- Sending image bytes to Jev.
- Calling OpenRouter's Decisions API. The client posts to thejevai.com.
- A stored history of prior tickets. The state includes `prior_tickets`, which the HTTP API leaves empty.

## Decisions

1. The inspection service calls Jev from Python (`backend/app/jev.py`) because `ticket.create` runs in `run_agent` before the browser sees the JSON. `src/lib/jev` is the typed client, parser, and fallback used by the UI copy and by `npm run test:jev`. The heuristic and the authority rules are duplicated in both places and covered by tests.
2. No key, or any request or parse failure, produces `source: "heuristic"` and `calibrated: false`. `JEV_PRIMARY` does not promote that heuristic over the office policy.
3. When `JEV_PRIMARY=1` and the source is Jev, confidence below 0.70 applies ESCALATE so a person reviews the mid band. Confidence at or above 0.70 applies the Jev choice.
4. An open panel measured by OpenCV stays ESCALATE even when Jev suggests CLEAR or HOLD. The aid cannot clear exposed gear.
5. The model id defaults to `jev-1.13.0`. `JEV_API_KEY` wins over `TYPESAFE_API_KEY`. One retry on HTTP 429 or 529, then the heuristic.
6. The aid is a card under the decision banner, labeled "Decision aid". Heuristic copy says it is not a calibrated model score.

## Risks / Trade-offs

- Two implementations of the heuristic can drift. Tests lock the CLEAR / HOLD / ESCALATE branches and the authority notes.
- A hosted call sees the measurement summary and trade, not the image. That is still site metadata. The README says so.
- `JEV_PRIMARY` can hold a case the office policy would clear, and can escalate a low-confidence case into a ticket. That is opt-in.

## Migration Plan

No data migration. Unset keys keep today's gate. Set `JEV_DUAL_RUN=1` before `JEV_PRIMARY=1`.

## Open Questions

- None for this change. A later change could pass real prior tickets into `run_agent` once FieldSight stores them.
