# Proposal

## Why

A service tech needs a jobsite photo to decide, in the next minute, whether the crew can keep working. The visual facts that matter (hi-vis vest, open electrical cover, warning label) should choose the next action, not sit in a chat explanation of a fixed label.

## What Changes

- Add a web inspection flow: pick a synthetic jobsite fixture or upload a photo.
- Measure the photo with OpenCV 5 (vest mask, panel contours, Canny interior density, warning-label regions).
- Run a perception → decision → action loop whose tool list changes with those measurements: CLEAR, HOLD, or ESCALATE, then an SMS draft and a clearance note.
- Store the photo through an S3-shaped path that works without credentials (local mock) and can use boto3, Lambda, and optional Bedrock phrasing.

## Capabilities

### New Capabilities

- `jobsite-inspection`: Photo in, OpenCV measurements, agent decision, SMS, and clearance note out.
- `image-storage`: S3-compatible storage of the inspection photo, with a credential-free local mock.

### Modified Capabilities

- None. This is the first FieldSight behavior.

## Impact

- Next.js UI, FastAPI service, OpenCV 5, boto3, and an optional Bedrock note pass.
- New HTTP surface: `GET /health`, `GET /v1/samples`, `POST /v1/inspections`, `POST /v1/inspections/samples/{id}`.
- No live SMS or ticket system. Those tools are simulated.
