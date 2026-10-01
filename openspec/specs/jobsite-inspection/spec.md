# jobsite-inspection Specification

## Purpose

Turn a jobsite photo into a CLEAR, HOLD, or ESCALATE decision whose following actions depend on what the image measurements found.

## Requirements

### Requirement: Photo inspection returns measurements and an overlay
The system MUST accept a JPEG, PNG, or WebP jobsite photo, or a named sample fixture, and return image measurements plus an annotated image.

#### Scenario: Sample fixture
- **WHEN** a client inspects a known sample fixture
- **THEN** the response includes vest coverage, panel candidates with edge density, warning-label regions, and an annotated image

#### Scenario: Unreadable upload
- **WHEN** a client uploads bytes that are not an image
- **THEN** the system rejects the request and does not produce a decision

### Requirement: Measurements choose the next action
The system MUST choose CLEAR, HOLD, or ESCALATE from the measurements, and the set of actions that run MUST change with that choice. An urgent ticket MUST be created only for ESCALATE. A text draft and a clearance note MUST be produced for every decision, and their content MUST differ by decision.

#### Scenario: Latched panel with vest and label
- **WHEN** vest coverage is at or above the torso threshold, the panel interior edge density is below the open-gear threshold, and a warning label is beside the panel
- **THEN** the decision is CLEAR and no urgent ticket is created

#### Scenario: Missing vest on a latched panel
- **WHEN** vest coverage is below the torso threshold and the panel is not open
- **THEN** the decision is HOLD and no urgent ticket is created

#### Scenario: Open panel
- **WHEN** a panel-shaped dark region has interior edge density at or above the open-gear threshold
- **THEN** the decision is ESCALATE and an urgent ticket is created whose id appears in the text draft

#### Scenario: No panel contour
- **WHEN** the measurements contain no panel-shaped region
- **THEN** the interior panel measurement is skipped

### Requirement: Trade changes the action text
The system MUST accept electrical, HVAC, or plumbing as the trade on the call. An open panel MUST still escalate on every trade. The ticket title and the text draft MUST name the trade.

#### Scenario: Open panel on a plumbing call
- **WHEN** the same open-panel measurements are inspected as a plumbing call
- **THEN** the decision stays ESCALATE and the text tells the crew to stop plumbing work and get a qualified electrical person

### Requirement: Human confirmation
The clearance note MUST state that a qualified person still has to confirm the equipment before anyone works it.

#### Scenario: Any decision
- **WHEN** an inspection completes
- **THEN** the clearance note includes that confirmation limit
