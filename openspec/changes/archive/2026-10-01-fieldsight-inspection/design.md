# Design

## Context

See proposal.md. The product has to run in a demo with no AWS account, and the same code has to be deployable where the photo lands in S3.

## Goals / Non-Goals

**Goals:**

- OpenCV returns measurements. A separate policy chooses tools.
- One HTTP API the Next.js app can proxy.
- Storage and an optional phrasing model are swappable by environment variables.

**Non-Goals:**

- Sending real SMS or opening a real work-order system.
- Training a detector.
- Authenticating techs.

## Decisions

- Python service plus Next.js UI. OpenCV 5 ships as `opencv-python-headless`. The browser only displays the overlay the service draws.
- Vision code does not emit CLEAR / HOLD / ESCALATE. The agent applies a 4% vest-coverage threshold and an 8% interior edge-density threshold, then calls `policy.check`, and only then `ticket.create` or a skip.
- Bedrock, when `BEDROCK_MODEL_ID` is set, may rephrase the clearance note. If the reply drops the decision word, the template stands. The model is not allowed to pick the decision.
- Local storage writes the same key layout the S3 client would use (`inspections/<sha>`) and returns `s3://fieldsight-local/...`. Real S3 is `put_object` via boto3, including an optional custom endpoint.
- Lambda is a thin handler around the same functions, not a second policy. Container image is the practical package because of the OpenCV wheel. Zip-size packaging is out of this demo.
- Sample photos are drawn with OpenCV and checked in, so the three-minute demo does not depend on a camera.

Alternatives considered: opencv.js in the browser (harder to keep the agent and the S3 path on one server), and a single vision label with a chat explanation (rejected because the tool list would not change).

## Risks / Trade-offs

- [Color masks false-positive on cones, fences, and yellow pipes] → The UI calls the result a screen, and the note requires a person to confirm. Limitations are written in docs/REPORT.md.
- [Synthetic fixtures match the masks too well] → Tests also drive the agent from raw measurement objects, so the branch is not only an artifact of the drawings.
- [OpenCV wheel is heavy for Lambda zip] → Handler is documented for a container image. The demo process is FastAPI.

## Migration Plan

No existing users. Deploy the API and the web app together. Rollback is stopping the processes. Enabling S3 or Bedrock is an environment change, not a schema change.

## Open Questions

None that change the spec. A later pass can replace the color masks with a trained detector without changing the tool contract, as long as it still emits coverage, edge density, and label boxes.
