"""OpenCV 5 jobsite measurements.

The module returns measurements and geometry. It does not decide CLEAR, HOLD,
or ESCALATE. The inspection agent reads these numbers and chooses the next tool.
"""

from __future__ import annotations

import base64
from typing import Any

import cv2
import numpy as np

MAX_WIDTH = 960

# Hi-vis orange in OpenCV's 0–180 hue range. Reflective yellow-green strips and
# warning-label yellow sit outside this band so a label is not counted as a vest.
VEST_ORANGE_LOW = (4, 140, 80)
VEST_ORANGE_HIGH = (22, 255, 255)

# Warning placards: saturated yellow, plus red for lockout tags.
LABEL_YELLOW_LOW = (22, 140, 140)
LABEL_YELLOW_HIGH = (32, 255, 255)
LABEL_RED_LOW_A = (0, 140, 90)
LABEL_RED_HIGH_A = (8, 255, 255)
LABEL_RED_LOW_B = (170, 140, 90)
LABEL_RED_HIGH_B = (180, 255, 255)

# Open gear reads as a dark rectangle. A latched cover reads as a light metal door.
DARK_LOW = (0, 0, 0)
DARK_HIGH = (180, 90, 75)
METAL_LOW = (0, 0, 175)
METAL_HIGH = (180, 45, 255)


def opencv_version() -> str:
    return cv2.__version__


def decode_image(data: bytes) -> np.ndarray:
    array = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode image. Use JPEG, PNG, or WebP.")
    return image


def _resize(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    if width <= MAX_WIDTH:
        return image
    scale = MAX_WIDTH / width
    return cv2.resize(image, (MAX_WIDTH, int(height * scale)), interpolation=cv2.INTER_AREA)


def _mask_contours(mask: np.ndarray) -> list[np.ndarray]:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return list(contours)


def _box_of(contour: np.ndarray) -> list[int]:
    x, y, w, h = cv2.boundingRect(contour)
    return [int(x), int(y), int(w), int(h)]


def _edge_density(edges: np.ndarray, box: list[int]) -> float:
    x, y, w, h = box
    roi = edges[y : y + h, x : x + w]
    if roi.size == 0:
        return 0.0
    return float((roi > 0).mean())


def _mask_fill(mask: np.ndarray, box: list[int]) -> float:
    x, y, w, h = box
    roi = mask[y : y + h, x : x + w]
    if roi.size == 0:
        return 0.0
    return float((roi > 0).mean())


def _passes_panel_shape(contour: np.ndarray, mask: np.ndarray, image_area: float) -> bool:
    area = cv2.contourArea(contour)
    ratio = area / image_area
    if ratio < 0.045 or ratio > 0.35:
        return False
    x, y, w, h = cv2.boundingRect(contour)
    if w < 40 or h < 40:
        return False
    aspect = w / h
    if aspect < 0.4 or aspect > 2.1:
        return False
    # A dark door frame or label border can enclose a large contour while the
    # mask itself is only a thin ring. Require the box to actually be filled.
    if _mask_fill(mask, [x, y, w, h]) < 0.5:
        return False
    extent = area / float(w * h)
    return extent >= 0.55


def _regions_from_mask(
    mask: np.ndarray,
    color: str,
    image_area: float,
) -> list[dict[str, Any]]:
    regions: list[dict[str, Any]] = []
    for contour in _mask_contours(mask):
        area = float(cv2.contourArea(contour))
        ratio = area / image_area
        if ratio < 0.0018 or ratio > 0.08:
            continue
        regions.append(
            {
                "color": color,
                "box": _box_of(contour),
                "area_ratio": round(ratio, 4),
            }
        )
    regions.sort(key=lambda item: item["area_ratio"], reverse=True)
    return regions


def _panel_candidates(
    mask: np.ndarray,
    kind: str,
    edges: np.ndarray,
    image_area: float,
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for contour in _mask_contours(mask):
        if not _passes_panel_shape(contour, mask, image_area):
            continue
        box = _box_of(contour)
        density = _edge_density(edges, box)
        found.append(
            {
                "kind": kind,
                "box": box,
                "area_ratio": round(float(cv2.contourArea(contour)) / image_area, 4),
                "edge_density": round(density, 4),
            }
        )
    found.sort(key=lambda item: item["edge_density"], reverse=True)
    return found


def analyze_bgr(image: np.ndarray) -> tuple[dict[str, Any], np.ndarray]:
    """Run vest, panel, and label measurements. Returns findings and an overlay."""
    working = _resize(image)
    height, width = working.shape[:2]
    image_area = float(height * width)
    hsv = cv2.cvtColor(working, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(working, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 60, 150)

    orange = cv2.inRange(hsv, VEST_ORANGE_LOW, VEST_ORANGE_HIGH)
    # Reflective strips are yellow-green, outside the warning-label yellow band.
    lime = cv2.inRange(hsv, (33, 120, 120), (48, 255, 255))
    orange = cv2.bitwise_or(orange, lime)
    vest_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    orange = cv2.morphologyEx(orange, cv2.MORPH_CLOSE, vest_kernel)
    orange = cv2.morphologyEx(
        orange,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
    )
    vest_contours = _mask_contours(orange)
    largest = max(vest_contours, key=cv2.contourArea) if vest_contours else None
    coverage = float(cv2.contourArea(largest) / image_area) if largest is not None else 0.0
    vest_box = _box_of(largest) if largest is not None and coverage >= 0.008 else None

    dark = cv2.inRange(hsv, DARK_LOW, DARK_HIGH)
    dark = cv2.morphologyEx(
        dark,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21)),
    )
    metal = cv2.inRange(hsv, METAL_LOW, METAL_HIGH)
    metal = cv2.morphologyEx(
        metal,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)),
    )
    panels = _panel_candidates(dark, "dark_rect", edges, image_area)
    panels.extend(_panel_candidates(metal, "metal_rect", edges, image_area))

    yellow = cv2.inRange(hsv, LABEL_YELLOW_LOW, LABEL_YELLOW_HIGH)
    red = cv2.bitwise_or(
        cv2.inRange(hsv, LABEL_RED_LOW_A, LABEL_RED_HIGH_A),
        cv2.inRange(hsv, LABEL_RED_LOW_B, LABEL_RED_HIGH_B),
    )
    label_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    yellow = cv2.morphologyEx(yellow, cv2.MORPH_CLOSE, label_kernel)
    red = cv2.morphologyEx(red, cv2.MORPH_CLOSE, label_kernel)
    labels = _regions_from_mask(yellow, "yellow", image_area)
    labels.extend(_regions_from_mask(red, "red", image_area))

    findings: dict[str, Any] = {
        "image": {"width": width, "height": height},
        "opencv": {
            "version": cv2.__version__,
            "stages": [
                "resize",
                "hsv_orange_vest_mask",
                "canny_edges",
                "dark_rect_contours",
                "metal_rect_contours",
                "yellow_red_label_mask",
            ],
        },
        "ppe_vest": {
            "coverage": round(coverage, 4),
            "box": vest_box,
            "contour_count": len(vest_contours),
        },
        "electrical_panel": {"candidates": panels},
        "warning_label": {"regions": labels},
        "edges": {"foreground_ratio": round(float((edges > 0).mean()), 4)},
    }
    overlay = _draw_overlay(working, findings, edges)
    return findings, overlay


def analyze_bytes(data: bytes) -> tuple[dict[str, Any], np.ndarray]:
    return analyze_bgr(decode_image(data))


def encode_jpeg_b64(image: np.ndarray) -> str:
    ok, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 86])
    if not ok:
        raise RuntimeError("Could not encode overlay")
    return base64.b64encode(buffer.tobytes()).decode("ascii")


def _draw_overlay(image: np.ndarray, findings: dict[str, Any], edges: np.ndarray) -> np.ndarray:
    overlay = image.copy()
    tint = image.copy()
    vest_box = findings["ppe_vest"]["box"]
    if vest_box is not None:
        x, y, w, h = vest_box
        cv2.rectangle(tint, (x, y), (x + w, y + h), (40, 170, 60), -1)
    cv2.addWeighted(tint, 0.28, overlay, 0.72, 0, overlay)

    if vest_box is not None:
        x, y, w, h = vest_box
        cv2.rectangle(overlay, (x, y), (x + w, y + h), (30, 170, 50), 2)

    for candidate in findings["electrical_panel"]["candidates"]:
        x, y, w, h = candidate["box"]
        color = (40, 40, 220) if candidate["kind"] == "dark_rect" else (180, 110, 20)
        cv2.rectangle(overlay, (x, y), (x + w, y + h), color, 2)

    for region in findings["warning_label"]["regions"]:
        x, y, w, h = region["box"]
        cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 200, 255), 2)

    # A thin edge map in the corner so the demo shows Canny was actually run.
    thumb = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
    thumb = cv2.resize(thumb, (160, 106), interpolation=cv2.INTER_AREA)
    overlay[8:114, 8:168] = cv2.addWeighted(overlay[8:114, 8:168], 0.35, thumb, 0.65, 0)
    cv2.rectangle(overlay, (8, 8), (168, 114), (255, 255, 255), 1)

    coverage = findings["ppe_vest"]["coverage"]
    panel_count = len(findings["electrical_panel"]["candidates"])
    label_count = len(findings["warning_label"]["regions"])
    caption = (
        f"OpenCV {cv2.__version__}  vest {coverage:.1%}  "
        f"panels {panel_count}  labels {label_count}"
    )
    cv2.rectangle(overlay, (0, overlay.shape[0] - 36), (overlay.shape[1], overlay.shape[0]), (20, 18, 16), -1)
    cv2.putText(
        overlay,
        caption,
        (12, overlay.shape[0] - 12),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (245, 240, 230),
        1,
        cv2.LINE_AA,
    )
    return overlay
