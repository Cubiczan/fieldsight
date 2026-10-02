## ADDED Requirements

### Requirement: Jev decision aid
The system MUST attach a decision aid after the office policy check. The aid MUST be computed from structured measurements (vest coverage, whether the panel is latched, trade, prior tickets, and a measurement summary) and MUST NOT require the photo. One evaluation MUST include a CLEAR, HOLD, or ESCALATE choice, a yes-or-no probability that the panel is open, a yes-or-no probability that the vest is missing, and an urgency score. The aid MUST be labeled as a decision aid and MUST NOT be described as a certainty. When no Jev API key is configured, or the Jev call fails, the system MUST fill the aid from deterministic local rules, mark it as not calibrated, and MUST keep the office policy as the gate that creates or skips the urgent ticket.

#### Scenario: Demo without a key
- **WHEN** an inspection runs without `JEV_API_KEY` and without `TYPESAFE_API_KEY`
- **THEN** the response includes a decision aid marked as a local heuristic, the CLEAR, HOLD, or ESCALATE gate matches the office policy, and no Jev HTTP call is made

#### Scenario: Open panel cannot be cleared by the aid
- **WHEN** the panel measurement is open and the decision aid suggests CLEAR or HOLD
- **THEN** the gate stays ESCALATE and an urgent ticket is still created

### Requirement: Optional Jev authority
When `JEV_DUAL_RUN` is set, the system MUST log both the office policy gate and the decision aid, and the office policy MUST remain the gate unless `JEV_PRIMARY` is also set. When `JEV_PRIMARY` is set and the aid came from Jev with calibrated confidence at or above 0.70, the aid's choice MUST set the gate, except that an open panel MUST stay ESCALATE. When `JEV_PRIMARY` is set and the calibrated confidence is below 0.70, the gate MUST be ESCALATE. A missing key or a failed call MUST NOT let `JEV_PRIMARY` replace the office policy.

#### Scenario: Dual run keeps the office policy
- **WHEN** `JEV_DUAL_RUN` is set, `JEV_PRIMARY` is not set, and the aid disagrees with the office policy
- **THEN** the logged comparison contains both gates and the urgent ticket still follows the office policy

#### Scenario: Primary high confidence
- **WHEN** `JEV_PRIMARY` is set and Jev returns HOLD with calibrated confidence at or above 0.70 on a latched panel that the office policy would clear
- **THEN** the gate is HOLD and no urgent ticket is created

#### Scenario: Low confidence escalates
- **WHEN** `JEV_PRIMARY` is set and Jev returns a choice with calibrated confidence below 0.70
- **THEN** the gate is ESCALATE
