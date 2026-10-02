## Why

FieldSight already turns OpenCV measurements into CLEAR, HOLD, or ESCALATE. That branch is a decision, and Jev (TypeSafe System One) is a text decision API with calibrated probabilities. The photo pipeline should stay where it is. Jev should only suggest or, when explicitly enabled, set the gate.

## What Changes

- Add a Choice / Score / Noul client that posts structured jobsite state to `https://thejevai.com/v1/systemone`, with a deterministic heuristic when no API key is set or the call fails.
- Run that aid after `policy.check` and before `ticket.create`. Default authority stays with the office policy. `JEV_DUAL_RUN=1` logs both. `JEV_PRIMARY=1` lets a high-confidence Jev choice set the gate, except an open panel stays ESCALATE.
- Show the aid in the UI as a decision aid with calibrated confidence when Jev answered, and as a local heuristic otherwise. Do not present it as a certainty.
- Leave OpenCV, SMS drafting, and ticket drafting in place.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `jobsite-inspection`: A decision aid sits on the existing measurements. The office policy remains the gate unless Jev is the configured primary and its confidence clears the threshold.

## Impact

- `src/lib/jev` and `backend/app/jev.py` add the client. `backend/app/agent.py` calls it inside the existing loop.
- The inspection JSON gains an `agent.jev` object. Ticket creation still follows the applied gate.
- New env vars: `JEV_API_KEY`, `TYPESAFE_API_KEY`, `JEV_DUAL_RUN`, `JEV_PRIMARY`, `JEV_MODEL`.
- No new paid dependency. A configured key bills about $0.042 per million input tokens.
