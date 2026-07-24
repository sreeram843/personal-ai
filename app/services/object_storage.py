from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Protocol
from uuid import uuid4

from app.core.config import Settings

logger = logging.getLogger(__name__)


class ObjectStorage(Protocol):
    def put_bytes(self, *, user_id: str, filename: str, payload: bytes, content_type: str | None = None) -> str:
        ...

    def get_uri(self, storage_key: str) -> str:
        ...


class LocalObjectStorage:
    def __init__(self, base_path: str) -> None:
        self._base = Path(base_path)
        self._base.mkdir(parents=True, exist_ok=True)

    def put_bytes(
        self,
        *,
        user_id: str,
        filename: str,
        payload: bytes,
        content_type: str | None = None,
    ) -> str:
        safe_name = Path(filename).name or "upload.bin"
        key = f"{user_id}/{uuid4().hex}_{safe_name}"
        target = self._base / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return key

    def get_uri(self, storage_key: str) -> str:
        return f"file://{self._base / storage_key}"

    def delete_user_prefix(self, user_id: str) -> int:
        user_dir = self._base / user_id
        if not user_dir.exists():
            return 0
        removed = 0
        for path in user_dir.rglob("*"):
            if path.is_file():
                path.unlink(missing_ok=True)
                removed += 1
        for path in sorted(user_dir.rglob("*"), reverse=True):
            if path.is_dir():
                path.rmdir()
        if user_dir.exists():
            user_dir.rmdir()
        return removed


class S3ObjectStorage:
    def __init__(
        self,
        *,
        bucket: str,
        prefix: str,
        endpoint_url: Optional[str],
        region: Optional[str],
        access_key: Optional[str],
        secret_key: Optional[str],
    ) -> None:
        import boto3

        session = boto3.session.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        self._client = session.client("s3", endpoint_url=endpoint_url)
        self._bucket = bucket
        self._prefix = prefix.strip("/")

    def put_bytes(
        self,
        *,
        user_id: str,
        filename: str,
        payload: bytes,
        content_type: str | None = None,
    ) -> str:
        safe_name = Path(filename).name or "upload.bin"
        key = f"{self._prefix}/{user_id}/{uuid4().hex}_{safe_name}"
        extra_args = {"ContentType": content_type} if content_type else None
        if extra_args:
            self._client.put_object(Bucket=self._bucket, Key=key, Body=payload, **extra_args)
        else:
            self._client.put_object(Bucket=self._bucket, Key=key, Body=payload)
        return key

    def get_uri(self, storage_key: str) -> str:
        return f"s3://{self._bucket}/{storage_key}"

    def delete_user_prefix(self, user_id: str) -> int:
        # Best-effort cleanup; operators can also purge via bucket lifecycle.
        prefix = f"{self._prefix}/{user_id}/".lstrip("/")
        removed = 0
        try:
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                objects = page.get("Contents") or []
                if not objects:
                    continue
                self._client.delete_objects(
                    Bucket=self._bucket,
                    Delete={"Objects": [{"Key": obj["Key"]} for obj in objects]},
                )
                removed += len(objects)
        except Exception:
            logger.exception("Failed deleting S3 objects for user %s", user_id)
        return removed


def build_object_storage(settings: Settings) -> ObjectStorage:
    if settings.object_storage_backend == "s3":
        if not settings.object_storage_bucket:
            raise ValueError("OBJECT_STORAGE_BUCKET is required when OBJECT_STORAGE_BACKEND=s3")
        return S3ObjectStorage(
            bucket=settings.object_storage_bucket,
            prefix=settings.object_storage_prefix,
            endpoint_url=settings.object_storage_endpoint_url,
            region=settings.object_storage_region,
            access_key=settings.object_storage_access_key,
            secret_key=settings.object_storage_secret_key,
        )
    return LocalObjectStorage(settings.object_storage_local_path)
