"""Backward-compatible branding aliases for the SPEC-12 storage inventory."""

from app.core.storage_access_inventory import (
    IMAGE_EXTENSIONS,
    MAX_IMAGE_SIZE_BYTES,
    ORGANIZATION_LOGOS_BUCKET,
)

BUCKET = ORGANIZATION_LOGOS_BUCKET
MAX_LOGO_SIZE_BYTES = MAX_IMAGE_SIZE_BYTES
ALLOWED_LOGO_CONTENT_TYPES = dict(IMAGE_EXTENSIONS)
