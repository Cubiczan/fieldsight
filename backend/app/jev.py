"""Jev (TypeSafe System One) decision aid for a jobsite inspection.

OpenCV still measures the photo. This module only sees the structured state
the agent already computed: vest coverage, panel latch, trade, prior tickets,
and a measurement summary. Choice / Score / Noul run in one POST to
https://thejevai.com/v1/systemone.

The typed twin of the parser, questions, and fallback lives in src/lib/jev.
Keep heuristic_decision and choose_gate aligned with that package.

No API key, or a failed call, fills the aid from the same local rules as
policy.check. The office policy stays the gate unless JEV_PRIMARY=1.
An open panel cannot be cleared by the aid.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any

DEFAULT_MODEL = "jev-1.13.0"
DEFAULT_URL = "https://thejevai.com/v1/systemone"
CONFIDENCE_MIN = 0.7
GATES = ("CLEAR", "HOLD", "ESCALATE")
SUM_TOLERANCE = 0.05

logger = logging.getLogger("fieldsight.jev")
logger.setLevel(logging.INFO)
if not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("fieldsight.jev %(message)s"))
    logger.addHandler(_handler)


class JevError(Exception):
    pass


class JevRetryable(JevError):
    def __init__(self, delay_s: float) -> None:
        super().__init__("rate limited")
        self.delay_s = delay_s


def api_key() -> str:
    return os.getenv("JEV_API_KEY", "").strip() or os.getenv("TYPESAFE_API_KEY", "").strip()


def env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def jobsite_questions() -> dict[str, Any]:
    return {
        "decision": {
            "type": "choice",
            "instructions": (
                "Which gate should the crew follow from these measurements? "
                "This is a decision aid, not a determination that equipment is safe to touch."
            ),
            "criteria": {
                "CLEAR": (
                    "Vest is present, the panel is latched or no panel is in frame, "
                    "and a warning label is beside the panel when a panel is in frame."
                ),
                "HOLD": (
                    "No exposed live gear, but a correctable gap remains, such as a missing vest "
                    "or a missing warning label. No urgent ticket."
                ),
                "ESCALATE": (
                    "The panel interior reads as open, or a person needs to stop work "
                    "and open an urgent office ticket."
                ),
            },
        },
        "open_panel": {
            "type": "noul",
            "instructions": "Does the structured state say the electrical panel interior is open (cover off)?",
            "criteria": {
                "true": "panel_state is open",
                "false": "panel_state is closed (latched) or none (no panel contour)",
            },
        },
        "vest_missing": {
            "type": "noul",
            "instructions": "Is a hi-vis vest missing from the photo?",
            "criteria": {
                "true": "vest_present is false or vest_coverage is below vest_threshold",
                "false": "vest_present is true and coverage meets the torso threshold",
            },
        },
        "urgency": {
            "type": "score",
            "instructions": "How urgent is a human follow-up, based only on these measurements and any prior tickets?",
            "criteria": [
                "Routine: vest, cover, and label are in order",
                "Correctable: a gap the crew can fix on site",
                "Urgent: exposed gear or a missing guard that should stop work",
                "Stop work: open panel, treat as an immediate office escalation",
            ],
        },
    }


def build_state(
    *,
    trade: str,
    vest_present: bool,
    vest_coverage: float,
    vest_threshold: float,
    panel_state: str,
    edge_density: float | None,
    open_edge_threshold: float,
    label_present: bool,
    prior_tickets: list[dict[str, Any]] | None,
    opencv_version: str,
    panel_candidates: int,
    label_regions: int,
) -> dict[str, Any]:
    tickets = list(prior_tickets or [])
    density = "n/a" if edge_density is None else f"{edge_density:.1%}"
    open_prior = sum(1 for item in tickets if item.get("status") == "open")
    summary = (
        f"{trade} call. Hi-vis coverage {vest_coverage:.1%} "
        f"({'present' if vest_present else 'absent'}, threshold {vest_threshold:.0%}). "
        f"Panel {panel_state}, interior edge density {density} "
        f"(open at {open_edge_threshold:.0%}). "
        f"Warning label beside equipment: {'yes' if label_present else 'no'}. "
        f"Prior open tickets: {open_prior}."
    )
    return {
        "trade": trade,
        "vest_present": vest_present,
        "vest_coverage": vest_coverage,
        "vest_threshold": vest_threshold,
        "panel_state": panel_state,
        "panel_latched": panel_state == "closed",
        "edge_density": edge_density,
        "open_edge_threshold": open_edge_threshold,
        "label_present": label_present,
        "prior_tickets": tickets,
        "measurement_summary": summary,
        "measurements": {
            "opencv_version": opencv_version,
            "panel_candidates": panel_candidates,
            "label_regions": label_regions,
        },
    }


def build_request(state: dict[str, Any], model: str | None = None) -> dict[str, Any]:
    return {
        "model": model or os.getenv("JEV_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        "state": state,
        "questions": jobsite_questions(),
    }


def heuristic_decision(state: dict[str, Any]) -> dict[str, Any]:
    """Match src/lib/jev/fallback.ts. An open panel escalates; other gaps hold."""
    panel = state.get("panel_state")
    vest_present = bool(state.get("vest_present"))
    label_present = bool(state.get("label_present"))
    if panel == "open":
        decision = "ESCALATE"
    elif (not vest_present) or (panel == "closed" and not label_present):
        decision = "HOLD"
    else:
        decision = "CLEAR"
    open_panel = {"open": 0.96, "closed": 0.04, "none": 0.02}.get(str(panel), 0.02)
    vest_missing = 0.04 if vest_present else 0.96
    base = {"CLEAR": 0.1, "HOLD": 1.15, "ESCALATE": 2.85}[decision]
    tickets = state.get("prior_tickets") or []
    open_priors = sum(1 for item in tickets if isinstance(item, dict) and item.get("status") == "open")
    urgency = min(3.0, round(base + open_priors * 0.25, 2))
    return {
        "decision": decision,
        "open_panel": open_panel,
        "vest_missing": vest_missing,
        "urgency": urgency,
    }


def _reading(heuristic: dict[str, Any], **extra: Any) -> dict[str, Any]:
    reading = {
        "source": "heuristic",
        "model": None,
        "decision": heuristic["decision"],
        "confidence": None,
        "calibrated": False,
        "open_panel": heuristic["open_panel"],
        "vest_missing": heuristic["vest_missing"],
        "urgency": heuristic["urgency"],
        "urgency_confidence": None,
    }
    reading.update(extra)
    return reading


def _probability(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise JevError(f"{label} is invalid")
    number = float(value)
    if number < 0 or number > 1:
        raise JevError(f"{label} is invalid")
    return number


def _probabilities(value: Any) -> dict[str, float]:
    if not isinstance(value, dict) or not value:
        raise JevError("probabilities must be an object")
    parsed = {str(key): _probability(item, f"probability for {key}") for key, item in value.items()}
    total = sum(parsed.values())
    if abs(total - 1) > SUM_TOLERANCE:
        raise JevError("probabilities must sum to 1")
    return parsed


def parse_systemone(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise JevError("response must be an object")
    model = raw.get("model")
    if not isinstance(model, str) or not model:
        raise JevError("response is missing model")
    answers = raw.get("answers")
    if not isinstance(answers, dict) or not answers:
        raise JevError("response is missing answers")
    usage = raw.get("usage")
    if not isinstance(usage, dict):
        raise JevError("response is missing usage")
    for name in ("input_tokens", "output_tokens"):
        tokens = usage.get(name)
        if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 0:
            raise JevError(f"usage.{name} is invalid")
    return {"model": model, "answers": answers, "usage": usage}


def reading_from_response(parsed: dict[str, Any]) -> dict[str, Any]:
    answers = parsed["answers"]
    decision = answers.get("decision")
    open_panel = answers.get("open_panel")
    vest_missing = answers.get("vest_missing")
    urgency = answers.get("urgency")
    if not isinstance(decision, dict) or decision.get("type") != "choice":
        raise JevError("decision choice must be CLEAR, HOLD, or ESCALATE")
    choice = decision.get("choice")
    if choice not in GATES:
        raise JevError("decision choice must be CLEAR, HOLD, or ESCALATE")
    probabilities = _probabilities(decision.get("probabilities"))
    if choice not in probabilities:
        raise JevError("choice is missing from probabilities")
    confidence = _probability(decision.get("confidence"), "choice confidence")
    if not isinstance(open_panel, dict) or open_panel.get("type") != "noul":
        raise JevError("open_panel must be a noul")
    if not isinstance(vest_missing, dict) or vest_missing.get("type") != "noul":
        raise JevError("vest_missing must be a noul")
    if not isinstance(urgency, dict) or urgency.get("type") != "score":
        raise JevError("urgency must be a score")
    score = urgency.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise JevError("score answer is missing score")
    return _reading(
        {
            "decision": choice,
            "open_panel": _probability(open_panel.get("noul"), "noul"),
            "vest_missing": _probability(vest_missing.get("noul"), "noul"),
            "urgency": float(score),
        },
        source="jev",
        model=parsed["model"],
        confidence=confidence,
        calibrated=True,
        urgency_confidence=_probability(urgency.get("confidence"), "score confidence"),
    )


def choose_gate(
    *,
    policy: str,
    reading: dict[str, Any],
    panel_state: str,
    primary: bool,
) -> tuple[str, str, str]:
    """Return applied decision, authority, and the note shown with the aid."""
    if not primary:
        return policy, "policy", "The office policy sets the gate. This result is a decision aid."
    if reading.get("source") != "jev":
        return policy, "policy", "Jev was not called, so the office policy stays the gate."
    if panel_state == "open" and reading.get("decision") != "ESCALATE":
        return (
            "ESCALATE",
            "policy",
            "The panel reads open, so the gate stays ESCALATE. This aid cannot clear exposed gear.",
        )
    confidence = reading.get("confidence")
    if confidence is None or float(confidence) < CONFIDENCE_MIN:
        return (
            "ESCALATE",
            "jev",
            "Calibrated confidence is below 0.70, so the gate escalates for a person to review.",
        )
    return (
        str(reading["decision"]),
        "jev",
        "JEV_PRIMARY is on and calibrated confidence is at least 0.70, so this aid sets the gate. "
        "It is not a determination that the equipment is safe to touch.",
    )


def _retry_delay(headers: Any) -> float:
    millis = headers.get("retry-after-ms") if headers is not None else None
    if millis not in (None, ""):
        try:
            return min(max(float(millis) / 1000.0, 0.0), 1.0)
        except (TypeError, ValueError):
            pass
    seconds = headers.get("retry-after") if headers is not None else None
    if seconds not in (None, ""):
        try:
            return min(max(float(seconds), 0.0), 1.0)
        except (TypeError, ValueError):
            pass
    return 0.2


def _post_once(payload: dict[str, Any]) -> dict[str, Any]:
    key = api_key()
    if not key:
        raise JevError("missing api key")
    url = os.getenv("JEV_API_URL", DEFAULT_URL).strip() or DEFAULT_URL
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "fieldsight/0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code in {429, 529}:
            raise JevRetryable(_retry_delay(exc.headers)) from exc
        raise JevError(f"status {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise JevError("network") from exc
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise JevError("invalid json") from exc
    if not isinstance(parsed, dict):
        raise JevError("response must be an object")
    return parsed


def post_systemone(payload: dict[str, Any]) -> dict[str, Any]:
    delay = 0.0
    for attempt in range(2):
        if delay:
            time.sleep(delay)
        try:
            return _post_once(payload)
        except JevRetryable as exc:
            if attempt == 1:
                raise JevError("rate limited") from exc
            delay = exc.delay_s
    raise JevError("unreachable")


def evaluate_jobsite(state: dict[str, Any], *, policy_decision: str) -> dict[str, Any]:
    """Return the decision aid. Network only when a key is set."""
    heuristic = heuristic_decision(state)
    reading = _reading(heuristic)
    key = api_key()
    if key:
        try:
            raw = post_systemone(build_request(state))
            reading = reading_from_response(parse_systemone(raw))
        except (JevError, ValueError, KeyError, TypeError):
            logger.info("jev call failed; local heuristic filled in")
            reading = _reading(heuristic)
    applied, authority, note = choose_gate(
        policy=policy_decision,
        reading=reading,
        panel_state=str(state.get("panel_state")),
        primary=env_flag("JEV_PRIMARY"),
    )
    aid = {
        **reading,
        "authority": authority,
        "applied_decision": applied,
        "policy_decision": policy_decision,
        "agrees_with_policy": reading["decision"] == policy_decision,
        "note": note,
    }
    if env_flag("JEV_DUAL_RUN") or env_flag("JEV_PRIMARY") or aid["source"] == "jev":
        confidence = "none" if aid["confidence"] is None else f"{float(aid['confidence']):.2f}"
        logger.info(
            "policy=%s aid=%s confidence=%s source=%s authority=%s applied=%s agree=%s",
            aid["policy_decision"],
            aid["decision"],
            confidence,
            aid["source"],
            aid["authority"],
            aid["applied_decision"],
            str(aid["agrees_with_policy"]).lower(),
        )
    return aid
