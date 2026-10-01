# FieldSight demo recording

About three minutes. One take, four fixture clicks, no upload. **Recording:** [`docs/fieldsight-demo.mp4`](./fieldsight-demo.mp4).

**YouTube (Public):** _pending upload — will be linked here._

## Before you hit record

1. From the repo root, start the app: `./scripts/dev.sh`
2. Open [http://127.0.0.1:43123](http://127.0.0.1:43123). Confirm the line under the trade buttons reads `OpenCV 5.0.0 · live analysis`. If it says the inspection service is not running, the API on port 43124 is down.
3. Hard-refresh once so fonts are cached. Scroll to the top. Do not click a fixture yet.
4. Window: 1920×1080, browser zoom 100%, bookmarks bar hidden. Record the browser window, not the whole desktop.
5. Dry-run the four clicks once, then scroll back to the top and start the recording.

Each fixture sets the trade itself. You do not need to press Electrical, HVAC, or Plumbing during the take.

Click **Show all** on shots 2–4 once the big decision word is on screen, so the trace does not eat the clock. On shot 1, let the steps appear on their own (about four seconds).

## Shot list

| Time | On screen | Do this | Say this |
| --- | --- | --- | --- |
| 0:00–0:18 | Header, headline, four fixtures | Hold on the top of the page. Point at the OpenCV version line. | "FieldSight is a jobsite check for HVAC, electrical, and plumbing. OpenCV reads the photo. The agent then picks the next action." |
| 0:18–0:55 | **Vest on, panel latched** | Click that card. Wait until the banner says **CLEAR**. Point at the green vest box, the blue latched cover, the yellow label, and the Canny thumbnail in the corner. Point at hi-vis coverage (about 6.8%) and panel edges (about 1.5%). | "Vest is in frame, the cover reads latched, the warning label is beside the gear. Edge density is under the 8% open-panel line. Policy says CLEAR, so the urgent ticket is skipped. The text goes to the office: crew can keep working." |
| 0:55–1:30 | **No hi-vis vest** | Click that card. Banner becomes **HOLD**. The trade pill switches to HVAC. Click **Show all**. Point at hi-vis coverage **0.0%** and at `ticket.create` still marked skipped. | "Same latched panel, same label. The only thing that changed is the vest. Coverage is zero, so the plan changes. HOLD, text the crew lead, still no office ticket." |
| 1:30–2:15 | **Open load center** | Click that card. Banner becomes **ESCALATE**. Trade returns to Electrical. Click **Show all**. Point at the red open-interior box and panel edges around 10%. Point at `ticket.create` marked executed, then at the SMS. | "Now the interior is dense with edges and there is no warning label. That measurement runs a different tool. Urgent ticket, and the text quotes the ticket id. Do not touch the gear." |
| 2:15–2:45 | **Vest on, cover off** | Click that card. Banner stays **ESCALATE**. Trade switches to Plumbing. Click **Show all**. Point at vest coverage back near 6.8%, and at the new SMS. | "The decision does not flip just because the vest is on. The cover is still off. The ticket title and the text change: stop the plumbing work and get a qualified electrical person." |
| 2:45–3:00 | Clearance note, storage line | Scroll to the note. Point at the `s3://fieldsight-local/...` line and the sentence about a qualified person. | "Locally that URI is a mock of S3. The same path writes to a real bucket when credentials are set. This is a screen for the crew, not a sign-off. A qualified person still confirms the equipment." |

Stop at 3:00. If you are early, hold on the clearance note. Do not add a fifth click.

## What each shot must show

- Shot 1: `ticket.create` is **skipped**. Decision **CLEAR**. Text recipient **office**.
- Shot 2: coverage **0.0%**. Decision **HOLD**. Recipient **crew-lead**. `ticket.create` still **skipped**.
- Shot 3: panel edges above **8%**. Decision **ESCALATE**. `ticket.create` is **executed**. SMS contains `FS-`.
- Shot 4: decision still **ESCALATE**, vest coverage above **4%**, SMS says the vest is on and names plumbing.

If a shot misses one of those, click the same card again. The run is deterministic for these fixtures.

## Stay out of the take

- Do not upload a personal photo. The colors are heuristics and a random room can confuse the three-minute story.
- Do not open the repo, the terminal, or `docs/REPORT.md` on camera. Mention AWS in the last line only.
- Do not claim the note is a lockout or that the gear is safe.

## After the recording

Demo file: [`docs/fieldsight-demo.mp4`](./fieldsight-demo.mp4) (H.264 slideshow with live app screenshots + narration captions). YouTube link filled after public upload.
