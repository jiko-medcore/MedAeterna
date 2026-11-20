"""Supabase Storage operations isolated from branding business rules."""

from uuid import UUID

from app.core.storage_upload_validation import (
    StorageUploadValidationError,
    validate_image_upload,
)
from app.core.supabase_admin import supabase_admin

from .constants import BUCKET

from .exceptions import InvalidLogoError



# ====================================================================================
# BRANDING STORAGE OPERATIONS
# ====================================================================================

# -----------------------------------------------------------------------------------
# Logo Validation
# -----------------------------------------------------------------------------------
def validate_logo(content_type: str | None, content: bytes) -> str:
    """Return the trusted extension after applying the upload safety policy."""
    try:
        return validate_image_upload(
            bucket=BUCKET,
            content_type=content_type,
            content=content,
        )
    except StorageUploadValidationError as exc:
        raise InvalidLogoError() from exc


# -----------------------------------------------------------------------------------
# Replace Organization Logo
# -----------------------------------------------------------------------------------
def replace_logo(*, organization_id: UUID, content_type: str, content: bytes) -> tuple[str, str]:
    """Store a deterministic per-organization logo and return its path and URL."""
    extension = validate_logo(content_type, content)
    path = f"{organization_id}/logo.{extension}"
    bucket = supabase_admin.storage.from_(BUCKET)
    bucket.upload(path=path, file=content, file_options={"content-type": content_type, "upsert": "true"})
    return path, bucket.get_public_url(path)


# -----------------------------------------------------------------------------------
# Delete Organization Logo
# -----------------------------------------------------------------------------------
def delete_logo(path: str) -> None:
    """Delete the internally stored path; this never accepts a public URL."""
    supabase_admin.storage.from_(BUCKET).remove([path])
