"""Perception → decision → action loop for a jobsite photo.

OpenCV hands this module measurements only. Thresholds and tool choice live
here, so a different vest coverage or panel edge density selects a different
tool sequence. An optional Jev call reads that structured state and returns a
CLEAR / HOLD / ESCALATE decision aid. The office policy stays the gate unless
JEV_PRIMARY=1. An optional Bedrock call can phrase the clearance note. It
cannot change the decision.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

from app.jev import build_state, evaluate_jobsite

# A torso-sized orange region. A hard hat or a small cone stays under this.
VEST_COVERAGE_MIN = 0.04
# Breaker rows and open conductors push Canny density well above a smooth door.
OPEN_EDGE_DENSITY_MIN = 0.08
LABEL_PAD_PX = 90

TRADE_LABELS = {
    "electrical": "electrical",
    "hvac": "HVAC",
    "plumbing": "plumbing",
}


def run_agent(
    findings: dict[str, Any],
    *,
    trade: str,
    image_uri: str,
    storage_mode: str,
    prior_tickets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    trade = trade if trade in TRADE_LABELS else "electrical"
    steps: list[dict[str, Any]] = []

    perception = _vision_read(findings)
    steps.append(perception)

    panel = _select_panel(findings)
    if panel is None:
        steps.append(
            _skipped(
                phase="perception",
                tool="panel.measure",
                reason="No panel-shaped region in the OpenCV contours, so interior edge measurement is skipped.",
            )
        )
        panel_state = "none"
        edge_density = None
        panel_box = None
    else:
        measured = _panel_measure(panel)
        steps.append(measured)
        panel_state = measured["output"]["state"]
        edge_density = measured["output"]["edge_density"]
        panel_box = measured["output"]["box"]

    vest_present = findings["ppe_vest"]["coverage"] >= VEST_COVERAGE_MIN
    label = _nearest_label(findings, panel_box)
    label_present = label is not None

    policy = _policy_check(
        trade=trade,
        vest_present=vest_present,
        vest_coverage=findings["ppe_vest"]["coverage"],
        panel_state=panel_state,
        edge_density=edge_density,
        label_present=label_present,
        label=label,
    )
    steps.append(policy)
    policy_decision = policy["output"]["decision"]
    jev_state = build_state(
        trade=trade,
        vest_present=vest_present,
        vest_coverage=findings["ppe_vest"]["coverage"],
        vest_threshold=VEST_COVERAGE_MIN,
        panel_state=panel_state,
        edge_density=edge_density,
        open_edge_threshold=OPEN_EDGE_DENSITY_MIN,
        label_present=label_present,
        prior_tickets=prior_tickets,
        opencv_version=str(findings["opencv"]["version"]),
        panel_candidates=len(findings["electrical_panel"]["candidates"]),
        label_regions=len(findings["warning_label"]["regions"]),
    )
    jev = evaluate_jobsite(jev_state, policy_decision=policy_decision)
    steps.append(_jev_step(jev))
    decision = jev["applied_decision"]

    inspection_id = _inspection_id(image_uri, trade, findings)
    ticket_payload = None
    if decision == "ESCALATE":
        ticket_step = _ticket_create(
            trade=trade,
            inspection_id=inspection_id,
            image_uri=image_uri,
            vest_present=vest_present,
            label_present=label_present,
            rules=policy["output"]["rules"],
            because=(
                "the Jev decision aid set ESCALATE"
                if jev["authority"] == "jev"
                else "policy.check returned ESCALATE"
            ),
        )
        steps.append(ticket_step)
        ticket_payload = ticket_step["output"]
    else:
        steps.append(
            _skipped(
                phase="action",
                tool="ticket.create",
                reason=(
                    "The gate returned CLEAR, so no office ticket is opened."
                    if decision == "CLEAR"
                    else "The gate returned HOLD. The crew can correct this on site, so no urgent ticket is opened."
                ),
            )
        )

    sms_step = _sms_draft(
        decision=decision,
        trade=trade,
        vest_present=vest_present,
        panel_state=panel_state,
        label_present=label_present,
        ticket=ticket_payload,
        inspection_id=inspection_id,
    )
    steps.append(sms_step)

    note_step = _clearance_write(
        decision=decision,
        trade=trade,
        inspection_id=inspection_id,
        image_uri=image_uri,
        storage_mode=storage_mode,
        findings=findings,
        vest_present=vest_present,
        panel_state=panel_state,
        edge_density=edge_density,
        label_present=label_present,
        ticket=ticket_payload,
        steps=steps,
        jev=jev,
    )
    steps.append(note_step)

    return {
        "inspection_id": inspection_id,
        "decision": decision,
        "trade": trade,
        "image_uri": image_uri,
        "storage": storage_mode,
        "jev": jev,
        "interpretation": {
            "vest_present": vest_present,
            "vest_coverage": findings["ppe_vest"]["coverage"],
            "vest_threshold": VEST_COVERAGE_MIN,
            "panel_state": panel_state,
            "edge_density": edge_density,
            "open_edge_threshold": OPEN_EDGE_DENSITY_MIN,
            "label_present": label_present,
            "label": label,
        },
        "steps": steps,
        "sms": sms_step["output"],
        "clearance_note": note_step["output"]["note"],
        "note_source": note_step["output"]["source"],
        "ticket": ticket_payload,
    }


def _vision_read(findings: dict[str, Any]) -> dict[str, Any]:
    vest = findings["ppe_vest"]
    panels = findings["electrical_panel"]["candidates"]
    labels = findings["warning_label"]["regions"]
    detail = (
        f"OpenCV {findings['opencv']['version']} measured hi-vis coverage "
        f"{vest['coverage']:.1%} across {vest['contour_count']} orange contours, "
        f"{len(panels)} panel-shaped regions, and {len(labels)} yellow or red placard regions."
    )
    return _executed(
        phase="perception",
        tool="vision.read",
        title="Read OpenCV measurements",
        detail=detail,
        tool_input={"stages": findings["opencv"]["stages"]},
        output={
            "coverage": vest["coverage"],
            "panel_candidates": len(panels),
            "label_regions": len(labels),
            "panel_box": _select_panel(findings)["box"] if _select_panel(findings) else None,
        },
    )


def _select_panel(findings: dict[str, Any]) -> dict[str, Any] | None:
    """Prefer an open-looking dark rectangle. Otherwise the largest metal door."""
    candidates = findings["electrical_panel"]["candidates"]
    dark = [item for item in candidates if item["kind"] == "dark_rect"]
    if dark:
        best = max(dark, key=lambda item: item["edge_density"])
        if best["edge_density"] >= OPEN_EDGE_DENSITY_MIN:
            return best
    metal = [item for item in candidates if item["kind"] == "metal_rect"]
    if metal:
        return max(metal, key=lambda item: item["area_ratio"])
    if dark:
        return max(dark, key=lambda item: item["area_ratio"])
    return None


def _panel_measure(panel: dict[str, Any]) -> dict[str, Any]:
    density = float(panel["edge_density"])
    state = "open" if panel["kind"] == "dark_rect" and density >= OPEN_EDGE_DENSITY_MIN else "closed"
    if state == "open":
        detail = (
            f"Interior edge density is {density:.1%}, above the {OPEN_EDGE_DENSITY_MIN:.0%} "
            "open-gear threshold. The cover is treated as off."
        )
    else:
        detail = (
            f"Interior edge density is {density:.1%}, below the {OPEN_EDGE_DENSITY_MIN:.0%} "
            "open-gear threshold. The cover is treated as latched."
        )
    return _executed(
        phase="perception",
        tool="panel.measure",
        title="Measure the panel interior",
        detail=detail,
        tool_input={"box": panel["box"], "kind": panel["kind"], "edge_density": density},
        output={"state": state, "edge_density": density, "box": panel["box"], "kind": panel["kind"]},
    )


def _nearest_label(findings: dict[str, Any], panel_box: list[int] | None) -> dict[str, Any] | None:
    if panel_box is None:
        return None
    px, py, pw, ph = panel_box
    best: dict[str, Any] | None = None
    best_distance = 1e9
    for region in findings["warning_label"]["regions"]:
        rx, ry, rw, rh = region["box"]
        cx = rx + rw / 2
        cy = ry + rh / 2
        inside = (px - LABEL_PAD_PX) <= cx <= (px + pw + LABEL_PAD_PX) and (
            py - LABEL_PAD_PX
        ) <= cy <= (py + ph + LABEL_PAD_PX)
        if not inside:
            continue
        distance = abs(cx - (px + pw / 2)) + abs(cy - (py + ph / 2))
        if distance < best_distance:
            best_distance = distance
            best = {**region, "distance_px": round(distance, 1)}
    return best


def _policy_check(
    *,
    trade: str,
    vest_present: bool,
    vest_coverage: float,
    panel_state: str,
    edge_density: float | None,
    label_present: bool,
    label: dict[str, Any] | None,
) -> dict[str, Any]:
    rules: list[dict[str, str]] = []
    if panel_state == "open":
        rules.append(
            {
                "id": "OSHA-1910.333",
                "severity": "critical",
                "detail": "Exposed electrical parts. Work around live gear stops until a qualified person guards or de-energizes it.",
            }
        )
    if panel_state in {"open", "closed"} and not label_present:
        rules.append(
            {
                "id": "NEC-110.16",
                "severity": "critical" if panel_state == "open" else "major",
                "detail": "No yellow or red warning placard beside the equipment.",
            }
        )
    if not vest_present:
        rules.append(
            {
                "id": "ANSI-ISEA-107",
                "severity": "major",
                "detail": f"Hi-vis coverage is {vest_coverage:.1%}, under the {VEST_COVERAGE_MIN:.0%} torso threshold.",
            }
        )

    if any(rule["severity"] == "critical" for rule in rules):
        decision = "ESCALATE"
    elif rules:
        decision = "HOLD"
    else:
        decision = "CLEAR"

    if decision == "ESCALATE":
        detail = "Critical rule fired. Next action is an urgent office ticket, then an SMS that quotes the ticket."
    elif decision == "HOLD":
        detail = "No critical exposure. Next action is an SMS to the crew lead. ticket.create will be skipped."
    else:
        detail = "Vest, cover, and label all pass. Next action is a short all-clear SMS. ticket.create will be skipped."

    return _executed(
        phase="decision",
        tool="policy.check",
        title="Check the jobsite policy",
        detail=detail,
        tool_input={
            "trade": trade,
            "vest_present": vest_present,
            "vest_coverage": vest_coverage,
            "panel_state": panel_state,
            "edge_density": edge_density,
            "label_present": label_present,
            "label_color": None if label is None else label["color"],
        },
        output={"decision": decision, "rules": rules},
    )


def _jev_step(jev: dict[str, Any]) -> dict[str, Any]:
    if jev["calibrated"] and jev["confidence"] is not None:
        confidence = f"calibrated confidence {float(jev['confidence']):.0%}"
    else:
        confidence = "local heuristic, not a calibrated score"
    return _executed(
        phase="decision",
        tool="jev.decide",
        title="Ask the Jev decision aid",
        detail=f"Decision aid {jev['decision']} ({confidence}). {jev['note']}",
        tool_input={
            "source": jev["source"],
            "model": jev["model"],
            "questions": ["decision", "open_panel", "vest_missing", "urgency"],
        },
        output=jev,
    )


def _ticket_create(
    *,
    trade: str,
    inspection_id: str,
    image_uri: str,
    vest_present: bool,
    label_present: bool,
    rules: list[dict[str, str]],
    because: str,
) -> dict[str, Any]:
    digest = hashlib.sha256(f"{inspection_id}:{trade}".encode()).hexdigest()[:4].upper()
    ticket_id = f"FS-{digest}"
    if trade == "plumbing":
        title = "Electrical exposure on a plumbing call"
    elif trade == "hvac":
        title = "Electrical exposure on an HVAC call"
    else:
        title = "Open electrical equipment"
    if vest_present and not label_present:
        summary = "Hi-vis vest is in frame. The panel reads open and no warning label was found."
    elif vest_present:
        summary = "Hi-vis vest is in frame, but the panel interior reads as open."
    else:
        summary = "Panel interior reads as open. Hi-vis vest was not found in the photo."
    return _executed(
        phase="action",
        tool="ticket.create",
        title="Open an urgent office ticket",
        detail=f"Created {ticket_id} because {because}.",
        tool_input={"priority": "urgent", "trade": trade, "image_uri": image_uri, "rules": [rule["id"] for rule in rules]},
        output={
            "id": ticket_id,
            "priority": "urgent",
            "title": title,
            "summary": summary,
            "status": "open",
        },
    )


def _sms_draft(
    *,
    decision: str,
    trade: str,
    vest_present: bool,
    panel_state: str,
    label_present: bool,
    ticket: dict[str, Any] | None,
    inspection_id: str,
) -> dict[str, Any]:
    trade_name = TRADE_LABELS[trade]
    if decision == "CLEAR":
        to = "office"
        body = (
            f"FieldSight CLEAR on the {trade_name} call ({inspection_id}). "
            "Hi-vis vest is in frame, the panel cover reads latched, and a warning label is beside the gear. "
            "Crew can keep working."
        )
    elif decision == "HOLD":
        to = "crew-lead"
        gaps = []
        if not vest_present:
            gaps.append("no hi-vis vest in the photo")
        if panel_state != "none" and not label_present:
            gaps.append("no warning label beside the equipment")
        if panel_state == "none" and vest_present:
            gaps.append("no equipment cover was in frame to judge")
        joined = " and ".join(gaps) if gaps else "a policy gap"
        body = (
            f"FieldSight HOLD on the {trade_name} call ({inspection_id}). "
            f"Issue: {joined}. Fix it and shoot the panel again. No office ticket yet."
        )
    else:
        to = "office-oncall"
        ticket_id = ticket["id"] if ticket else "pending"
        if trade == "plumbing":
            who = "Stop the plumbing work and get a qualified electrical person."
        elif trade == "hvac":
            who = "Stop the HVAC work and get a qualified electrical person."
        else:
            who = "Do not touch the gear."
        vest_line = "Vest is on." if vest_present else "No hi-vis vest in the photo."
        label_line = "Warning label is missing." if not label_present else "A warning label is visible, but the cover is off."
        article = "an" if trade in {"electrical", "hvac"} else "a"
        body = (
            f"FieldSight ESCALATE ({inspection_id}). Ticket {ticket_id}. "
            f"Open electrical gear on {article} {trade_name} call. {vest_line} {label_line} {who}"
        )
    return _executed(
        phase="action",
        tool="sms.draft",
        title="Draft the text",
        detail=f"Drafted a {decision} text to {to}. The wording comes from the policy branch, not a fixed script.",
        tool_input={"decision": decision, "to": to, "ticket_id": None if ticket is None else ticket["id"]},
        output={"to": to, "body": body},
    )


def _clearance_write(
    *,
    decision: str,
    trade: str,
    inspection_id: str,
    image_uri: str,
    storage_mode: str,
    findings: dict[str, Any],
    vest_present: bool,
    panel_state: str,
    edge_density: float | None,
    label_present: bool,
    ticket: dict[str, Any] | None,
    steps: list[dict[str, Any]],
    jev: dict[str, Any],
) -> dict[str, Any]:
    density_text = "n/a" if edge_density is None else f"{edge_density:.1%}"
    executed = [step["tool"] for step in steps if step["status"] == "executed"]
    skipped = [step["tool"] for step in steps if step["status"] == "skipped"]
    template = "\n".join(
        [
            "FIELDSIGHT CLEARANCE NOTE",
            f"Inspection: {inspection_id}",
            f"Trade: {TRADE_LABELS[trade]}",
            f"Decision: {decision}",
            f"Image: {image_uri}",
            f"Storage: {storage_mode}",
            "",
            f"OpenCV {findings['opencv']['version']}",
            f"- Hi-vis coverage: {findings['ppe_vest']['coverage']:.1%} (threshold {VEST_COVERAGE_MIN:.0%}) → {'present' if vest_present else 'absent'}",
            f"- Panel: {panel_state}, interior edge density {density_text} (open at {OPEN_EDGE_DENSITY_MIN:.0%})",
            f"- Warning label beside equipment: {'yes' if label_present else 'no'}",
            "",
            "Tools run: " + ", ".join(executed),
            "Tools skipped: " + (", ".join(skipped) if skipped else "none"),
            f"Ticket: {ticket['id'] if ticket else 'none'}",
            _aid_line(jev),
            "",
            _decision_line(decision),
            "",
            "Photo heuristic for the crew. A qualified person still has to confirm the equipment before anyone works it.",
        ]
    )
    note, source = _maybe_polish_with_bedrock(template, decision)
    return _executed(
        phase="action",
        tool="clearance.write",
        title="Write the clearance note",
        detail="The note records the measurements and which tools the branch actually ran.",
        tool_input={"decision": decision, "source": source},
        output={"note": note, "source": source},
    )


def _aid_line(jev: dict[str, Any]) -> str:
    if jev["calibrated"] and jev["confidence"] is not None:
        score = f"calibrated confidence {float(jev['confidence']):.0%}"
    else:
        score = "local heuristic, not a calibrated score"
    return f"Decision aid: {jev['decision']} ({score}). Authority: {jev['authority']}. {jev['note']}"


def _decision_line(decision: str) -> str:
    if decision == "CLEAR":
        return "Release: crew may continue this task."
    if decision == "HOLD":
        return "Hold: correct the gap in the photo and run FieldSight again before continuing."
    return "Stop: do not work the equipment. Office follows the urgent ticket."


def _maybe_polish_with_bedrock(note: str, decision: str) -> tuple[str, str]:
    """Optional phrasing pass. The decision line is fixed before this call."""
    model_id = os.getenv("BEDROCK_MODEL_ID", "").strip()
    if not model_id:
        return note, "template"
    try:
        import boto3

        region = os.getenv("BEDROCK_REGION", os.getenv("AWS_REGION", "us-east-1"))
        client = boto3.client("bedrock-runtime", region_name=region)
        response = client.converse(
            modelId=model_id,
            system=[
                {
                    "text": (
                        "You edit a jobsite clearance note for clarity. "
                        f"The decision is {decision} and you must keep that exact decision word. "
                        "Do not add hazards that are not in the note. Keep it under 180 words."
                    )
                }
            ],
            messages=[{"role": "user", "content": [{"text": note}]}],
            inferenceConfig={"maxTokens": 400, "temperature": 0.2},
        )
        polished = response["output"]["message"]["content"][0]["text"].strip()
        if decision not in polished:
            return note, "template"
        return polished, "bedrock"
    except Exception:
        return note, "template"


def _inspection_id(image_uri: str, trade: str, findings: dict[str, Any]) -> str:
    payload = f"{image_uri}|{trade}|{findings['ppe_vest']['coverage']}|{len(findings['electrical_panel']['candidates'])}"
    return "INS-" + hashlib.sha256(payload.encode()).hexdigest()[:8].upper()


def _executed(
    *,
    phase: str,
    tool: str,
    title: str,
    detail: str,
    tool_input: dict[str, Any],
    output: dict[str, Any],
) -> dict[str, Any]:
    return {
        "phase": phase,
        "tool": tool,
        "status": "executed",
        "title": title,
        "detail": detail,
        "input": tool_input,
        "output": output,
    }


def _skipped(*, phase: str, tool: str, reason: str) -> dict[str, Any]:
    titles = {
        "panel.measure": "Measure the panel interior",
        "ticket.create": "Open an urgent office ticket",
    }
    return {
        "phase": phase,
        "tool": tool,
        "status": "skipped",
        "title": titles.get(tool, tool),
        "detail": reason,
        "input": {},
        "output": {},
    }
