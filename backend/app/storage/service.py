from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from backend.app.storage.context import StorageContext, load_storage_context


@dataclass(frozen=True)
class StorageService:
    context: StorageContext

    @classmethod
    def from_env(cls) -> "StorageService":
        return cls(load_storage_context())

    @classmethod
    def unconfigured(cls) -> "StorageService":
        return cls(
            StorageContext(
                provider="backblaze_b2",
                bucket_name=None,
                endpoint=None,
                prefix="artifacts/dev",
                access_key_id=None,
                secret_access_key=None,
            )
        )

    @property
    def is_configured(self) -> bool:
        return self.context.is_configured

    def require_configured(self) -> None:
        if not self.is_configured:
            raise RuntimeError("storage is not configured")

    def describe(self) -> dict[str, object]:
        return {
            "provider": self.context.provider,
            "bucket_name": self.context.bucket_name,
            "endpoint": self.context.endpoint,
            "prefix": self.context.prefix,
            "status": "configured" if self.is_configured else "unconfigured",
        }

    def build_key(self, *parts: str) -> str:
        normalized_parts = [segment.strip("/") for segment in parts if segment.strip("/")]
        if self.context.prefix:
            normalized_parts.insert(0, self.context.prefix)
        return str(PurePosixPath(*normalized_parts))

    def upload_bytes(self, *, key: str, payload: bytes, content_type: str) -> dict[str, object]:
        if not self.is_configured:
            raise RuntimeError("object storage is not configured")
        if not payload:
            raise ValueError("payload is required")
        if not content_type:
            raise ValueError("content_type is required")
        return {
            "provider": self.context.provider,
            "bucket_name": self.context.bucket_name,
            "endpoint": self.context.endpoint,
            "object_key": self.build_key(key),
            "content_type": content_type,
            "size_bytes": len(payload),
            "status": "staged",
        }
