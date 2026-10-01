"""Vision measurements must change the agent's tools, not just the wording."""

from __future__ import annotations

import cv2
from fastapi.testclient import TestClient

from app.agent import VEST_COVERAGE_MIN, run_agent
from app.main import app
from app.samples import SAMPLES, samples_dir
from app.vision import analyze_bgr


def _tool(agent: dict, name: str) -> dict:
    matches = [step for step in agent["steps"] if step["tool"] == name]
    assert matches, name
    return matches[-1]


def _findings(**overrides):
    findings = {
        "image": {"width": 960, "height": 640},
        "opencv": {"version": "5.0.0", "stages": ["test"]},
        "ppe_vest": {"coverage": 0.08, "box": [10, 10, 100, 200], "contour_count": 1},
        "electrical_panel": {
            "candidates": [
                {
                    "kind": "metal_rect",
                    "box": [400, 100, 180, 260],
                    "area_ratio": 0.08,
                    "edge_density": 0.02,
                }
            ]
        },
        "warning_label": {"regions": [{"color": "yellow", "box": [600, 120, 80, 50], "area_ratio": 0.006}]},
        "edges": {"foreground_ratio": 0.04},
    }
    findings.update(overrides)
    return findings


def test_agent_changes_tools_when_measurements_change():
    clear = run_agent(
        _findings(),
        trade="electrical",
        image_uri="s3://fieldsight-local/clear.png",
        storage_mode="local-mock",
    )
    assert clear["decision"] == "CLEAR"
    assert _tool(clear, "ticket.create")["status"] == "skipped"
    assert _tool(clear, "sms.draft")["output"]["to"] == "office"

    hold_findings = _findings()
    hold_findings["ppe_vest"] = {"coverage": VEST_COVERAGE_MIN - 0.01, "box": None, "contour_count": 0}
    hold = run_agent(
        hold_findings,
        trade="hvac",
        image_uri="s3://fieldsight-local/hold.png",
        storage_mode="local-mock",
    )
    assert hold["decision"] == "HOLD"
    assert _tool(hold, "ticket.create")["status"] == "skipped"
    assert _tool(hold, "sms.draft")["output"]["to"] == "crew-lead"
    assert "vest" in hold["sms"]["body"].lower()

    escalate_findings = _findings()
    escalate_findings["ppe_vest"] = {"coverage": 0.0, "box": None, "contour_count": 0}
    escalate_findings["electrical_panel"] = {
        "candidates": [
            {
                "kind": "dark_rect",
                "box": [400, 100, 180, 260],
                "area_ratio": 0.1,
                "edge_density": 0.14,
            }
        ]
    }
    escalate_findings["warning_label"] = {"regions": []}
    escalate = run_agent(
        escalate_findings,
        trade="electrical",
        image_uri="s3://fieldsight-local/open.png",
        storage_mode="local-mock",
    )
    assert escalate["decision"] == "ESCALATE"
    assert _tool(escalate, "ticket.create")["status"] == "executed"
    assert escalate["ticket"]["priority"] == "urgent"
    assert escalate["ticket"]["id"] in escalate["sms"]["body"]
    assert {clear["sms"]["body"], hold["sms"]["body"], escalate["sms"]["body"]} == {
        clear["sms"]["body"],
        hold["sms"]["body"],
        escalate["sms"]["body"],
    }
    assert len({clear["sms"]["body"], hold["sms"]["body"], escalate["sms"]["body"]}) == 3


def test_no_panel_skips_interior_measurement():
    findings = _findings(electrical_panel={"candidates": []}, warning_label={"regions": []})
    agent = run_agent(
        findings,
        trade="plumbing",
        image_uri="s3://fieldsight-local/none.png",
        storage_mode="local-mock",
    )
    assert _tool(agent, "panel.measure")["status"] == "skipped"
    assert agent["decision"] == "CLEAR"


def test_trade_changes_escalate_ticket_without_changing_decision():
    findings = _findings()
    findings["electrical_panel"] = {
        "candidates": [
            {"kind": "dark_rect", "box": [400, 100, 180, 260], "area_ratio": 0.1, "edge_density": 0.2}
        ]
    }
    findings["warning_label"] = {"regions": []}
    electrical = run_agent(
        findings,
        trade="electrical",
        image_uri="s3://fieldsight-local/open.png",
        storage_mode="s3",
    )
    plumbing = run_agent(
        findings,
        trade="plumbing",
        image_uri="s3://fieldsight-local/open.png",
        storage_mode="s3",
    )
    assert electrical["decision"] == plumbing["decision"] == "ESCALATE"
    assert electrical["ticket"]["title"] != plumbing["ticket"]["title"]
    assert "plumbing" in plumbing["sms"]["body"].lower()
    assert "qualified electrical" in plumbing["sms"]["body"].lower()


def test_fixture_images_match_expected_decisions():
    seen = {}
    for sample in SAMPLES:
        image = cv2.imread(str(samples_dir() / sample["file"]))
        assert image is not None, sample["file"]
        findings, overlay = analyze_bgr(image)
        assert findings["opencv"]["version"].startswith("5.")
        assert overlay.shape[0] == image.shape[0]
        agent = run_agent(
            findings,
            trade=sample["trade"],
            image_uri=f"s3://fieldsight-local/{sample['file']}",
            storage_mode="local-mock",
        )
        seen[sample["id"]] = agent
        assert agent["decision"] == sample["expected"]

    assert _tool(seen["clear-ready"], "ticket.create")["status"] == "skipped"
    assert _tool(seen["hold-ppe"], "ticket.create")["status"] == "skipped"
    assert _tool(seen["escalate-open"], "ticket.create")["status"] == "executed"
    assert _tool(seen["escalate-vest-open"], "ticket.create")["status"] == "executed"
    assert seen["escalate-open"]["sms"]["body"] != seen["escalate-vest-open"]["sms"]["body"]
    assert seen["escalate-vest-open"]["interpretation"]["vest_present"] is True
    assert seen["escalate-open"]["interpretation"]["vest_present"] is False
    assert seen["clear-ready"]["interpretation"]["panel_state"] == "closed"
    assert seen["escalate-open"]["interpretation"]["panel_state"] == "open"
    assert seen["clear-ready"]["interpretation"]["edge_density"] < seen["escalate-open"]["interpretation"]["edge_density"]


def test_api_samples_and_upload(tmp_path, monkeypatch):
    monkeypatch.setenv("FIELDSIGHT_UPLOAD_DIR", str(tmp_path))
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("FIELDSIGHT_S3_BUCKET", raising=False)
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["opencv"].startswith("5.")

    listing = client.get("/v1/samples")
    assert listing.status_code == 200
    samples = listing.json()["samples"]
    assert {item["id"] for item in samples} == {item["id"] for item in SAMPLES}

    decisions = {}
    for sample in samples:
        response = client.post(f"/v1/inspections/samples/{sample['id']}?trade={sample['trade']}")
        assert response.status_code == 200, response.text
        body = response.json()
        decisions[sample["id"]] = body["agent"]["decision"]
        assert body["overlay_jpeg_base64"]
        assert body["agent"]["storage"] == "local-mock"
        assert body["agent"]["image_uri"].startswith("s3://fieldsight-local/inspections/")

    assert decisions["clear-ready"] == "CLEAR"
    assert decisions["hold-ppe"] == "HOLD"
    assert decisions["escalate-open"] == "ESCALATE"
    assert decisions["escalate-vest-open"] == "ESCALATE"

    image_path = samples_dir() / "escalate-open.png"
    with image_path.open("rb") as handle:
        upload = client.post(
            "/v1/inspections",
            files={"file": ("escalate-open.png", handle, "image/png")},
            data={"trade": "plumbing"},
        )
    assert upload.status_code == 200, upload.text
    uploaded = upload.json()["agent"]
    assert uploaded["decision"] == "ESCALATE"
    assert uploaded["ticket"]["title"].startswith("Electrical exposure on a plumbing")
    stored = list(tmp_path.rglob("*.png"))
    assert stored, "upload should be written to the local S3 mock"

    missing = client.post("/v1/inspections/samples/not-a-scene")
    assert missing.status_code == 404
    bad = client.post("/v1/inspections", files={"file": ("note.txt", b"not-an-image", "text/plain")})
    assert bad.status_code == 400
