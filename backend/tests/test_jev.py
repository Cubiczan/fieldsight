"""Jev parses System One answers and does not replace policy.check unless asked."""

from __future__ import annotations

import logging

import pytest

from app.agent import run_agent
from app.jev import (
    JevError,
    JevRetryable,
    build_request,
    build_state,
    evaluate_jobsite,
    heuristic_decision,
    parse_systemone,
    post_systemone,
    reading_from_response,
)


def _state(**overrides):
    state = build_state(
        trade="electrical",
        vest_present=True,
        vest_coverage=0.08,
        vest_threshold=0.04,
        panel_state="closed",
        edge_density=0.02,
        open_edge_threshold=0.08,
        label_present=True,
        prior_tickets=[],
        opencv_version="5.0.0",
        panel_candidates=1,
        label_regions=1,
    )
    state.update(overrides)
    return state


def _findings(**overrides):
    findings = {
        "image": {"width": 960, "height": 640},
        "opencv": {"version": "5.0.0", "stages": ["test"]},
        "ppe_vest": {"coverage": 0.08, "box": [10, 10, 100, 200], "contour_count": 1},
        "electrical_panel": {
            "candidates": [
                {"kind": "metal_rect", "box": [400, 100, 180, 260], "area_ratio": 0.08, "edge_density": 0.02}
            ]
        },
        "warning_label": {"regions": [{"color": "yellow", "box": [600, 120, 80, 50], "area_ratio": 0.006}]},
    }
    findings.update(overrides)
    return findings


def _response(choice="HOLD", confidence=0.81, noul_open=0.07, noul_vest=0.9, score=1.2):
    return {
        "model": "jev-1.13.0",
        "answers": {
            "decision": {
                "type": "choice",
                "choice": choice,
                "probabilities": {"CLEAR": 0.1, "HOLD": 0.84, "ESCALATE": 0.06}
                if choice == "HOLD"
                else {"CLEAR": 0.9, "HOLD": 0.08, "ESCALATE": 0.02},
                "confidence": confidence,
            },
            "open_panel": {"type": "noul", "noul": noul_open},
            "vest_missing": {"type": "noul", "noul": noul_vest},
            "urgency": {
                "type": "score",
                "score": score,
                "legend": {"0": "Routine", "1": "Correctable", "2": "Urgent", "3": "Stop work"},
                "probabilities": {"0": 0.05, "1": 0.75, "2": 0.15, "3": 0.05},
                "confidence": 0.7,
            },
        },
        "usage": {"input_tokens": 280, "output_tokens": 0},
    }


def _run(findings, **kwargs):
    return run_agent(
        findings,
        trade=kwargs.pop("trade", "electrical"),
        image_uri="s3://fieldsight-local/jev.png",
        storage_mode="local-mock",
        **kwargs,
    )


def test_parse_mixed_response_and_reject_bad_choice():
    parsed = parse_systemone(_response())
    reading = reading_from_response(parsed)
    assert reading["source"] == "jev"
    assert reading["calibrated"] is True
    assert reading["decision"] == "HOLD"
    assert reading["confidence"] == 0.81
    assert reading["open_panel"] == 0.07
    assert reading["vest_missing"] == 0.9
    assert reading["urgency"] == 1.2

    broken = _response()
    broken["answers"]["decision"]["choice"] = "WAIVE"
    with pytest.raises(JevError, match="CLEAR, HOLD, or ESCALATE"):
        reading_from_response(parse_systemone(broken))

    summed = _response()
    summed["answers"]["open_panel"]["noul"] = 1.4
    with pytest.raises(JevError, match="noul"):
        reading_from_response(parse_systemone(summed))


def test_request_asks_choice_noul_and_score_without_the_policy_answer():
    request = build_request(_state())
    assert request["model"] == "jev-1.13.0"
    assert set(request["questions"]) == {"decision", "open_panel", "vest_missing", "urgency"}
    assert request["questions"]["decision"]["type"] == "choice"
    assert request["questions"]["open_panel"]["type"] == "noul"
    assert request["questions"]["vest_missing"]["type"] == "noul"
    assert request["questions"]["urgency"]["type"] == "score"
    assert "policy_decision" not in request["state"]
    assert request["state"]["panel_latched"] is True


def test_heuristic_matches_policy_branches():
    assert heuristic_decision(_state())["decision"] == "CLEAR"
    assert heuristic_decision(_state(vest_present=False))["decision"] == "HOLD"
    assert heuristic_decision(_state(label_present=False))["decision"] == "HOLD"
    opened = _state(panel_state="open", panel_latched=False, vest_present=False, label_present=False)
    assert heuristic_decision(opened)["decision"] == "ESCALATE"
    assert heuristic_decision(opened)["open_panel"] == 0.96
    missing_panel = _state(panel_state="none", panel_latched=False, edge_density=None, label_present=False)
    assert heuristic_decision(missing_panel)["decision"] == "CLEAR"
    with_ticket = _state(prior_tickets=[{"id": "FS-1", "status": "open"}])
    assert heuristic_decision(with_ticket)["decision"] == "CLEAR"
    assert heuristic_decision(with_ticket)["urgency"] == 0.35


def test_no_key_keeps_policy_and_marks_the_aid_as_a_heuristic():
    agent = _run(_findings())
    assert agent["decision"] == "CLEAR"
    assert agent["jev"]["source"] == "heuristic"
    assert agent["jev"]["calibrated"] is False
    assert agent["jev"]["confidence"] is None
    assert agent["jev"]["authority"] == "policy"
    assert agent["jev"]["applied_decision"] == "CLEAR"
    step = next(item for item in agent["steps"] if item["tool"] == "jev.decide")
    assert "Decision aid" in step["detail"]
    assert "not a calibrated score" in step["detail"]
    assert "Decision aid:" in agent["clearance_note"]
    assert "qualified person" in agent["clearance_note"]


def test_dual_run_logs_both_and_keeps_policy(monkeypatch, caplog):
    monkeypatch.setenv("JEV_API_KEY", "test-key")
    monkeypatch.setenv("JEV_DUAL_RUN", "1")
    monkeypatch.setattr("app.jev.post_systemone", lambda payload: _response("HOLD", 0.88))
    caplog.set_level(logging.INFO, logger="fieldsight.jev")
    agent = _run(_findings())
    assert agent["decision"] == "CLEAR"
    assert agent["jev"]["decision"] == "HOLD"
    assert agent["jev"]["authority"] == "policy"
    assert agent["ticket"] is None
    assert "policy=CLEAR" in caplog.text
    assert "aid=HOLD" in caplog.text


def test_primary_high_confidence_sets_hold(monkeypatch):
    monkeypatch.setenv("JEV_API_KEY", "test-key")
    monkeypatch.setenv("JEV_PRIMARY", "1")
    monkeypatch.setattr("app.jev.post_systemone", lambda payload: _response("HOLD", 0.88))
    agent = _run(_findings())
    assert agent["decision"] == "HOLD"
    assert agent["jev"]["authority"] == "jev"
    assert agent["ticket"] is None
    assert agent["sms"]["to"] == "crew-lead"


def test_primary_low_confidence_escalates(monkeypatch):
    monkeypatch.setenv("JEV_API_KEY", "test-key")
    monkeypatch.setenv("JEV_PRIMARY", "1")
    monkeypatch.setattr("app.jev.post_systemone", lambda payload: _response("HOLD", 0.42))
    agent = _run(_findings())
    assert agent["decision"] == "ESCALATE"
    assert agent["ticket"]["priority"] == "urgent"
    assert "Jev decision aid" in next(step["detail"] for step in agent["steps"] if step["tool"] == "ticket.create")


def test_primary_cannot_clear_an_open_panel(monkeypatch):
    monkeypatch.setenv("JEV_API_KEY", "test-key")
    monkeypatch.setenv("JEV_PRIMARY", "1")
    monkeypatch.setattr("app.jev.post_systemone", lambda payload: _response("CLEAR", 0.99))
    findings = _findings()
    findings["electrical_panel"] = {
        "candidates": [
            {"kind": "dark_rect", "box": [400, 100, 180, 260], "area_ratio": 0.1, "edge_density": 0.2}
        ]
    }
    agent = _run(findings)
    assert agent["decision"] == "ESCALATE"
    assert agent["jev"]["decision"] == "CLEAR"
    assert agent["jev"]["authority"] == "policy"
    assert "cannot clear exposed gear" in agent["jev"]["note"]
    assert agent["ticket"]["id"] in agent["sms"]["body"]


def test_api_failure_falls_back_even_when_primary(monkeypatch):
    monkeypatch.setenv("JEV_API_KEY", "test-key")
    monkeypatch.setenv("JEV_PRIMARY", "1")

    def explode(payload):
        raise JevError("status 500")

    monkeypatch.setattr("app.jev.post_systemone", explode)
    agent = _run(_findings())
    assert agent["decision"] == "CLEAR"
    assert agent["jev"]["source"] == "heuristic"
    assert agent["jev"]["authority"] == "policy"


def test_post_retries_rate_limit_once(monkeypatch):
    calls = {"n": 0}

    def once(payload):
        calls["n"] += 1
        if calls["n"] == 1:
            raise JevRetryable(0)
        return {"ok": True}

    monkeypatch.setattr("app.jev._post_once", once)
    assert post_systemone({"state": "x"}) == {"ok": True}
    assert calls["n"] == 2


def test_typesafe_key_is_accepted(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "safe-key")
    seen = {}

    def capture(payload):
        seen["model"] = payload["model"]
        return _response("CLEAR", 0.91)

    monkeypatch.setattr("app.jev.post_systemone", capture)
    aid = evaluate_jobsite(_state(), policy_decision="CLEAR")
    assert seen["model"] == "jev-1.13.0"
    assert aid["source"] == "jev"
    assert aid["agrees_with_policy"] is True
