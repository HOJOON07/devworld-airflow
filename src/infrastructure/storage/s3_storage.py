from __future__ import annotations

import boto3
from botocore.config import Config as BotoConfig

from src.shared.config import StorageConfig
from src.shared.logging import setup_logging

logger = setup_logging(__name__)


class S3Storage:
    def __init__(self, config: StorageConfig) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=config.endpoint_url,
            aws_access_key_id=config.access_key,
            aws_secret_access_key=config.secret_key,
            config=BotoConfig(signature_version="s3v4"),
        )

    def put_object(self, bucket: str, key: str, data: bytes) -> None:
        logger.info("Uploading to s3://%s/%s (%d bytes)", bucket, key, len(data))
        self._client.put_object(Bucket=bucket, Key=key, Body=data)

    def get_object(self, bucket: str, key: str) -> bytes:
        logger.info("Downloading from s3://%s/%s", bucket, key)
        response = self._client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()

    def list_objects(self, bucket: str, prefix: str) -> list[str]:
        logger.info("Listing s3://%s/%s", bucket, prefix)
        paginator = self._client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys
