"""Draw the four synthetic jobsite fixtures used by the demo and tests.

Run from the repo root:

    python backend/scripts/generate_samples.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.samples import SAMPLES, samples_dir  # noqa: E402

WIDTH = 960
HEIGHT = 640


def hsv_bgr(h: int, s: int, v: int) -> tuple[int, int, int]:
    pixel = np.uint8([[[h, s, v]]])
    bgr = cv2.cvtColor(pixel, cv2.COLOR_HSV2BGR)[0, 0]
    return int(bgr[0]), int(bgr[1]), int(bgr[2])


def canvas(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    wall = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    wall[:] = hsv_bgr(18, 18, 150)
    for x in range(0, WIDTH, 19):
        shift = int(rng.integers(-10, 10))
        wall[:, x : x + 19] = np.clip(wall[:, x : x + 19].astype(np.int16) + shift, 0, 255)
    noise = rng.normal(0, 4, wall.shape)
    image = np.clip(wall.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    # Baseboard and a couple of conduits, kept thin so they are not panel candidates.
    cv2.rectangle(image, (0, 575), (WIDTH, HEIGHT), hsv_bgr(18, 25, 90), -1)
    cv2.line(image, (70, 40), (70, 575), hsv_bgr(0, 0, 70), 3)
    cv2.line(image, (110, 40), (110, 575), hsv_bgr(0, 0, 80), 3)
    cv2.line(image, (70, 80), (110, 80), hsv_bgr(0, 0, 75), 3)
    return image


def draw_person(image: np.ndarray, vest: bool) -> None:
    cv2.circle(image, (290, 148), 40, hsv_bgr(14, 60, 175), -1)
    cv2.rectangle(image, (240, 430), (340, 575), hsv_bgr(20, 40, 55), -1)
    if vest:
        cv2.rectangle(image, (205, 185), (375, 430), hsv_bgr(12, 230, 235), -1)
        cv2.rectangle(image, (205, 250), (375, 272), hsv_bgr(36, 200, 235), -1)
        cv2.rectangle(image, (205, 340), (375, 360), hsv_bgr(36, 180, 220), -1)
    else:
        cv2.rectangle(image, (205, 185), (375, 430), hsv_bgr(108, 160, 140), -1)
        cv2.rectangle(image, (230, 210), (350, 250), hsv_bgr(108, 80, 170), -1)


def draw_closed_panel(image: np.ndarray) -> tuple[int, int, int, int]:
    x, y, w, h = 590, 130, 190, 280
    cv2.rectangle(image, (x, y), (x + w, y + h), hsv_bgr(100, 10, 210), -1)
    cv2.rectangle(image, (x, y), (x + w, y + h), hsv_bgr(0, 0, 35), 6)
    for cx, cy in ((x + 16, y + 16), (x + w - 16, y + 16), (x + 16, y + h - 16), (x + w - 16, y + h - 16)):
        cv2.circle(image, (cx, cy), 5, hsv_bgr(0, 0, 80), -1)
    cv2.rectangle(image, (x + w // 2 - 10, y + 110), (x + w // 2 + 10, y + 170), hsv_bgr(0, 0, 60), -1)
    return x, y, w, h


def draw_open_panel(image: np.ndarray) -> tuple[int, int, int, int]:
    x, y, w, h = 580, 120, 210, 310
    cv2.rectangle(image, (x - 8, y - 8), (x + w + 8, y + h + 8), hsv_bgr(0, 0, 55), -1)
    cv2.rectangle(image, (x, y), (x + w, y + h), hsv_bgr(0, 0, 22), -1)
    for index, yy in enumerate(range(y + 18, y + h - 14, 15)):
        cv2.line(image, (x + 12, yy), (x + w - 12, yy), hsv_bgr(0, 0, 185), 2)
        toggle = hsv_bgr(100, 190, 190) if index % 2 == 0 else hsv_bgr(58, 150, 160)
        cv2.rectangle(image, (x + 22, yy - 5), (x + 52, yy + 5), toggle, -1)
    return x, y, w, h


def draw_label(image: np.ndarray, x: int, y: int) -> None:
    cv2.rectangle(image, (x, y), (x + 108, y + 68), hsv_bgr(27, 240, 240), -1)
    cv2.rectangle(image, (x, y), (x + 108, y + 68), (10, 10, 10), 3)
    for offset in range(0, 108, 18):
        cv2.line(image, (x + offset, y + 68), (x + offset + 24, y), (15, 15, 15), 3)
    cv2.putText(
        image,
        "WARNING",
        (x + 10, y + 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (10, 10, 10),
        2,
        cv2.LINE_AA,
    )


def render(sample_id: str) -> np.ndarray:
    image = canvas(seed={"clear-ready": 1, "hold-ppe": 2, "escalate-open": 3, "escalate-vest-open": 4}[sample_id])
    draw_person(image, vest=sample_id in {"clear-ready", "escalate-vest-open"})
    if sample_id in {"clear-ready", "hold-ppe"}:
        x, y, w, h = draw_closed_panel(image)
        draw_label(image, x + w + 18, y + 24)
    else:
        draw_open_panel(image)
    cv2.putText(
        image,
        "SYNTHETIC FIXTURE",
        (180, 36),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        hsv_bgr(0, 0, 70),
        2,
        cv2.LINE_AA,
    )
    return image


def main() -> None:
    destination = samples_dir()
    destination.mkdir(parents=True, exist_ok=True)
    for sample in SAMPLES:
        image = render(sample["id"])
        path = destination / sample["file"]
        cv2.imwrite(str(path), image)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
