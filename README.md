# FieldSight

Jobsite inspection for HVAC, electrical, and plumbing crews. A tech grabs a photo of the work area. OpenCV 5 measures the hi-vis vest, the electrical panel interior, and any warning label. An agent reads those measurements and then **chooses the next tool**: clear the task, hold for a fix, or escalate with an urgent office ticket, an SMS draft, and a clearance note.

The photo changes the plan. A latched panel skips `ticket.create`. An open panel runs it. A vest that is present changes the SMS and the ticket summary, even when the decision stays ESCALATE.

A Jev decision aid can read those measurements after OpenCV and suggest CLEAR, HOLD, or ESCALATE with a calibrated confidence. It does not see the photo, and it does not write the text or the ticket. The office policy still routes the work unless you set `JEV_PRIMARY=1`.

Built by Cubiczan / Sam Desigan for the OpenCV AI Competition 2026 (powered by AWS), Agentic Vision Award.

## Demo in about three minutes

The shot list, narration, and what each click must show are in [docs/DEMO.md](docs/DEMO.md).

1. **Vest on, panel latched** → CLEAR. `ticket.create` is skipped.
2. **No hi-vis vest** → HOLD. Coverage is 0%. Still no ticket.
3. **Open load center** → ESCALATE. `ticket.create` runs and the text quotes the ticket id.
4. **Vest on, cover off** → still ESCALATE, but the ticket and the text change because the vest is on and the call is plumbing.

**Demo video:** [`docs/fieldsight-demo.mp4`](docs/fieldsight-demo.mp4) · YouTube: [https://youtu.be/KivhSEd1OTs](https://youtu.be/KivhSEd1OTs)

## Run locally

Requirements: Node.js 22+, Python 3.12.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python backend/scripts/generate_samples.py

npm install
```

Two processes. The web app proxies `/api/vision/*` to the API.

```bash
# terminal 1
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 43124

# terminal 2
npm run dev
```

Or both at once:

```bash
./scripts/dev.sh
```

App: [http://127.0.0.1:43123](http://127.0.0.1:43123)

API health: [http://127.0.0.1:43124/health](http://127.0.0.1:43124/health)

No AWS credentials are required. Uploads land in `var/uploads/` and the note records an `s3://fieldsight-local/...` URI. To write to real S3 (or MinIO / LocalStack), copy `.env.example` to `.env` and set `FIELDSIGHT_S3_BUCKET`, `AWS_ACCESS_KEY_ID`, and `AWS_SECRET_ACCESS_KEY`. Set `BEDROCK_MODEL_ID` only if you want Bedrock to phrase the clearance note. It cannot flip CLEAR / HOLD / ESCALATE.

## Jev decision aid

Jev (TypeSafe System One) is a text decision API, not a vision model. FieldSight still measures the photo with OpenCV. After that, one request can ask four questions in parallel: a Choice of CLEAR, HOLD, or ESCALATE, a Noul for an open panel, a Noul for a missing vest, and a Score for urgency. The screen labels the result **Decision aid** and shows a calibrated confidence when the call succeeded. That number is a probability, not a certainty, and it does not mean the equipment is safe to touch.

Create a key at [thejevai.com](https://thejevai.com) or in the TypeSafe console at [console.typesafe.ai/keys](https://console.typesafe.ai/keys). Put it in the environment of the inspection service (the FastAPI process, or Lambda):

```bash
JEV_API_KEY=...
# TYPESAFE_API_KEY works as a fallback name for the same bearer token
```

The client posts to `https://thejevai.com/v1/systemone` and pins `jev-1.13.0` (`JEV_MODEL` overrides that). OpenRouter also hosts the model (`~typesafe/jev-latest`); this client does not speak the OpenRouter Decisions request shape.

| Variable | Effect |
| --- | --- |
| `JEV_API_KEY` or `TYPESAFE_API_KEY` | Bearer token. With neither set, a local heuristic fills the aid and the demo still runs. |
| `JEV_DUAL_RUN=1` | Call Jev (or the heuristic), log the office gate and the aid, and keep the office policy. |
| `JEV_PRIMARY=1` | A Jev choice with calibrated confidence of at least 0.70 sets the gate. Below 0.70, the gate escalates for a person. An open panel measured by OpenCV stays ESCALATE. |
| `JEV_MODEL` | Model id. Default `jev-1.13.0`. |

A failed call, or a missing key with `JEV_PRIMARY=1`, leaves the office policy in charge. Ticket text and the clearance note still come from the existing templates. Bedrock, when set, only phrases the note.

Cost is about **$0.042 per million input tokens**, and **$0 for output tokens**. One inspection sends a short JSON state, on the order of a few hundred tokens, so a call is a fraction of a cent. The bill tracks state size times how often you inspect, not a per-decision fee.

```bash
npm run test:jev
```

## Tests

```bash
source .venv/bin/activate
cd backend && pytest -q
```

The tests check that fixture photos produce different decisions, that `ticket.create` runs only on an open panel, and that the upload path stores bytes in the local S3 mock. `npm run test:jev` checks the TypeScript client parser and the no-key heuristic.

## Layout

```
src/                  Next.js UI
src/lib/jev           Choice, Score, and Noul client, parser, and fallback
backend/app/vision.py OpenCV measurements (no decision)
backend/app/agent.py  perception → policy.check → jev.decide → ticket / sms / note
backend/app/jev.py    System One call used by the inspection service
backend/app/store.py  S3 or local mock
backend/lambda_handler.py
public/samples/       synthetic jobsite fixtures
docs/DEMO.md           three-minute recording script
docs/fieldsight-demo.mp4   ~3 min demo (screenshots + captions)
docs/REPORT.md        technical report
```

## License

MIT. See [LICENSE](LICENSE).
