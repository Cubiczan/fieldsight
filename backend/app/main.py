"""FieldSight HTTP API."""

from __future__ import annotations

import hashlib
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.agent import run_agent
from app.samples import SAMPLES, sample_by_id, sample_path
from app.store import get_store
from app.vision import analyze_bytes, encode_jpeg_b64, opencv_version

TRADES = {"electrical", "hvac", "plumbing"}
MAX_BYTES = 10 * 1024 * 1024

app = FastAPI(title="FieldSight", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "fieldsight", "opencv": opencv_version()}


@app.get("/v1/samples")
def list_samples() -> dict[str, Any]:
    return {
        "samples": [
            {
                "id": sample["id"],
                "title": sample["title"],
                "scene": sample["scene"],
                "trade": sample["trade"],
                "expected": sample["expected"],
                "image_url": f"/samples/{sample['file']}",
            }
            for sample in SAMPLES
        ]
    }


@app.post("/v1/inspections/samples/{sample_id}")
def inspect_sample(sample_id: str, trade: str = "electrical") -> dict[str, Any]:
    sample = sample_by_id(sample_id)
    path = sample_path(sample_id)
    if sample is None or path is None or not path.is_file():
        raise HTTPException(status_code=404, detail=f"Unknown sample '{sample_id}'.")
    chosen = _trade(trade or sample["trade"])
    return _inspect(path.read_bytes(), chosen, filename=sample["file"])


@app.post("/v1/inspections")
async def inspect_upload(
    file: UploadFile = File(...),
    trade: str = Form("electrical"),
) -> dict[str, Any]:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Upload an image file.")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 10 MB or smaller.")
    return _inspect(data, _trade(trade), filename=file.filename or "upload.jpg")


def _trade(value: str) -> str:
    cleaned = value.strip().lower()
    if cleaned not in TRADES:
        raise HTTPException(status_code=400, detail="Trade must be electrical, hvac, or plumbing.")
    return cleaned


def _inspect(data: bytes, trade: str, filename: str) -> dict[str, Any]:
    try:
        findings, overlay = analyze_bytes(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    digest = hashlib.sha256(data).hexdigest()[:16]
    suffix = ".jpg" if not filename.lower().endswith(".png") else ".png"
    key = f"inspections/{digest}{suffix}"
    store = get_store()
    content_type = "image/png" if suffix == ".png" else "image/jpeg"
    image_uri = store.put_image(data, key, content_type)
    agent = run_agent(findings, trade=trade, image_uri=image_uri, storage_mode=store.mode)
    return {
        "overlay_jpeg_base64": encode_jpeg_b64(overlay),
        "findings": findings,
        "agent": agent,
    }
