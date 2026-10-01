# FieldSight

Jobsite inspection for HVAC, electrical, and plumbing crews. A tech grabs a photo of the work area. OpenCV 5 measures the hi-vis vest, the electrical panel interior, and any warning label. An agent reads those measurements and then **chooses the next tool**: clear the task, hold for a fix, or escalate with an urgent office ticket, an SMS draft, and a clearance note.

The photo changes the plan. A latched panel skips `ticket.create`. An open panel runs it. A vest that is present changes the SMS and the ticket summary, even when the decision stays ESCALATE.

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

## Tests

```bash
source .venv/bin/activate
cd backend && pytest -q
```

The tests check that fixture photos produce different decisions, that `ticket.create` runs only on an open panel, and that the upload path stores bytes in the local S3 mock.

## Layout

```
src/                  Next.js UI
backend/app/vision.py OpenCV measurements (no decision)
backend/app/agent.py  perception → policy.check → ticket / sms / note
backend/app/store.py  S3 or local mock
backend/lambda_handler.py
public/samples/       synthetic jobsite fixtures
docs/DEMO.md           three-minute recording script
docs/fieldsight-demo.mp4   ~3 min demo (screenshots + captions)
docs/REPORT.md        technical report
```

## License

MIT. See [LICENSE](LICENSE).
