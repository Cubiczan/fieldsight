"""AWS Lambda entry for an S3 ObjectCreated event.

Package this file with the `app` package and the dependencies in
requirements.txt (OpenCV manylinux wheel). Set FIELDSIGHT_TRADE and, if you
want the note polished, BEDROCK_MODEL_ID. The handler writes
`<key>.inspection.json` next to the uploaded photo.

This module is the production shape. The local demo uses FastAPI in app.main
and does not invoke Lambda.
"""

from __future__ import annotations

import json
import os
from urllib.parse import unquote_plus

import boto3

from app.agent import run_agent
from app.vision import analyze_bytes


def handler(event, context):
    del context
    record = event["Records"][0]
    bucket = record["s3"]["bucket"]["name"]
    key = unquote_plus(record["s3"]["object"]["key"])
    if key.endswith(".inspection.json"):
        return {"skipped": True, "reason": "result object"}

    s3 = boto3.client("s3")
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    findings, _overlay = analyze_bytes(body)
    trade = os.getenv("FIELDSIGHT_TRADE", "electrical")
    agent = run_agent(
        findings,
        trade=trade,
        image_uri=f"s3://{bucket}/{key}",
        storage_mode="s3",
    )
    result = {"findings": findings, "agent": agent}
    out_key = f"{key}.inspection.json"
    s3.put_object(
        Bucket=bucket,
        Key=out_key,
        Body=json.dumps(result).encode(),
        ContentType="application/json",
    )
    return {"decision": agent["decision"], "result_key": out_key}
