"""Trusted-side upload validation for inventoried media buckets.

Bucket limits configured in Postgres are enforced by the Storage service, but
they do not inspect file bytes. This module applies the second layer: reject a
declared type that disagrees with the file signature and derive the stored
extension from the validated type rather than from the upload filename.
"""

from __future__ import annotations

from app.core.storage_access_inventory import (
    IMAGE_SIGNATURES,
    STORAGE_BUCKET_INVENTORY,
)


class StorageUploadValidationError(ValueError):
    """Raised when an upload does not satisfy its bucket policy."""


def content_type_matches_signature(content_type: str, content: bytes) -> bool:
    """Return whether the bytes carry the expected magic bytes for the type."""
    checks = IMAGE_SIGNATURES.get(content_type)
    if checks is None:
        return False
    return all(
        len(content) >= offset + len(signature)
        and content[offset : offset + len(signature)] == signature
        for offset, signature in checks
    )


def validate_image_upload(*, bucket: str, content_type: str | None, content: bytes) -> str:
    """Validate an upload and return the trusted extension for its object path."""
    rule = STORAGE_BUCKET_INVENTORY.get(bucket)
    if rule is None:
        raise StorageUploadValidationError("unknown storage bucket")

    if content_type not in rule.allowed_mime_types:
        raise StorageUploadValidationError("unsupported content type")
    if not content or len(content) > rule.file_size_limit:
        raise StorageUploadValidationError("invalid file size")
    if not content_type_matches_signature(content_type, content):
        raise StorageUploadValidationError("content does not match its declared type")

    return rule.extension_by_mime[content_type]
