"""S3-compatible Bronze storage client for Supabase Storage (bucket: gus-bronze)."""

from __future__ import annotations

import gzip
import hashlib
import json
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from src.core.settings import Settings, get_settings


class BronzeStorageClient:
    """Reads and writes gzipped JSON payloads in Supabase S3 Storage."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.supabase_s3_endpoint:
            raise ValueError("SUPABASE_S3_ENDPOINT is not configured in .env")
        if not self.settings.supabase_s3_access_key_id or not self.settings.supabase_s3_secret_access_key:
            raise ValueError("SUPABASE_S3_ACCESS_KEY_ID / SECRET_ACCESS_KEY are not configured in .env")

        self.bucket = self.settings.supabase_storage_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=self.settings.supabase_s3_endpoint,
            region_name=self.settings.supabase_s3_region,
            aws_access_key_id=self.settings.supabase_s3_access_key_id,
            aws_secret_access_key=self.settings.supabase_s3_secret_access_key,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def check_bucket_access(self) -> bool:
        """Verify that the target Bronze bucket is reachable."""
        self.client.head_bucket(Bucket=self.bucket)
        return True

    def exists(self, key: str) -> bool:
        """Check whether an object already exists in the Bronze bucket."""
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def put_json_gz(self, key: str, payload: Any) -> str:
        """Compress payload as UTF-8 JSON (.json.gz), upload to S3, return SHA-256."""
        raw_bytes = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        sha256 = hashlib.sha256(raw_bytes).hexdigest()
        gz_bytes = gzip.compress(raw_bytes)
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=gz_bytes,
            ContentType="application/json",
            ContentEncoding="gzip",
            Metadata={"payload-sha256": sha256},
        )
        return sha256

    def get_json_gz(self, key: str) -> Any:
        """Download and decompress a .json.gz object from Bronze storage."""
        resp = self.client.get_object(Bucket=self.bucket, Key=key)
        body = resp["Body"].read()
        try:
            raw_bytes = gzip.decompress(body)
        except OSError:
            raw_bytes = body
        return json.loads(raw_bytes.decode("utf-8"))

    @staticmethod
    def dbw_data_key(id_zmienna: int, id_przekroj: int, year: int, id_okres: int) -> str:
        return f"gus_dbw/var={id_zmienna}/sec={id_przekroj}/year={year}/period={id_okres}/payload.json.gz"

    @staticmethod
    def dbw_dict_key(dict_name: str) -> str:
        return f"gus_dbw/dictionaries/{dict_name}/latest.json.gz"

    @staticmethod
    def nbp_rates_key(currency: str, year: int) -> str:
        return f"nbp/currency={currency.upper()}/year={year}/rates.json.gz"

