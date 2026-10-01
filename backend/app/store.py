"""Image storage.

Production path is S3 (or any S3-compatible endpoint such as MinIO). Local
demo runs write the same key layout to disk and return an s3:// URI so the
rest of the pipeline does not change.
"""

from __future__ import annotations

import os
from pathlib import Path


class LocalStore:
    mode = "local-mock"

    def __init__(self, root: Path) -> None:
        self.root = root
        self.bucket = os.getenv("FIELDSIGHT_S3_BUCKET", "fieldsight-local").strip() or "fieldsight-local"

    def put_image(self, data: bytes, key: str, content_type: str) -> str:
        del content_type  # The local mock keeps the bytes; content type is for S3 metadata.
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return f"s3://{self.bucket}/{key}"


class S3Store:
    mode = "s3"

    def __init__(self, bucket: str, region: str, endpoint_url: str | None) -> None:
        import boto3

        self.bucket = bucket
        self.client = boto3.client("s3", region_name=region, endpoint_url=endpoint_url or None)

    def put_image(self, data: bytes, key: str, content_type: str) -> str:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        return f"s3://{self.bucket}/{key}"


def get_store() -> LocalStore | S3Store:
    bucket = os.getenv("FIELDSIGHT_S3_BUCKET", "").strip()
    access_key = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    if bucket and access_key:
        return S3Store(
            bucket=bucket,
            region=os.getenv("AWS_REGION", "us-east-1"),
            endpoint_url=os.getenv("AWS_ENDPOINT_URL", "").strip() or None,
        )
    root = Path(os.getenv("FIELDSIGHT_UPLOAD_DIR", "")).expanduser() if os.getenv("FIELDSIGHT_UPLOAD_DIR") else _default_upload_root()
    return LocalStore(root)


def _default_upload_root() -> Path:
    return Path(__file__).resolve().parents[2] / "var" / "uploads"
