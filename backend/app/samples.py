"""Synthetic jobsite fixtures shipped with the demo."""

from __future__ import annotations

from pathlib import Path

SAMPLES: list[dict[str, str]] = [
    {
        "id": "clear-ready",
        "file": "clear-ready.png",
        "title": "Vest on, panel latched",
        "scene": "Mechanical room. Hi-vis vest in frame, cover closed, warning label beside the gear.",
        "trade": "electrical",
        "expected": "CLEAR",
    },
    {
        "id": "hold-ppe",
        "file": "hold-ppe.png",
        "title": "No hi-vis vest",
        "scene": "Same latched panel and label, but the tech is in a blue work shirt.",
        "trade": "hvac",
        "expected": "HOLD",
    },
    {
        "id": "escalate-open",
        "file": "escalate-open.png",
        "title": "Open load center",
        "scene": "Cover off, breaker rows exposed, no warning label, no hi-vis vest.",
        "trade": "electrical",
        "expected": "ESCALATE",
    },
    {
        "id": "escalate-vest-open",
        "file": "escalate-vest-open.png",
        "title": "Vest on, cover off",
        "scene": "Hi-vis is on, but the panel is open and the warning label is missing.",
        "trade": "plumbing",
        "expected": "ESCALATE",
    },
]


def samples_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "public" / "samples"


def sample_by_id(sample_id: str) -> dict[str, str] | None:
    for sample in SAMPLES:
        if sample["id"] == sample_id:
            return sample
    return None


def sample_path(sample_id: str) -> Path | None:
    sample = sample_by_id(sample_id)
    if sample is None:
        return None
    return samples_dir() / sample["file"]
