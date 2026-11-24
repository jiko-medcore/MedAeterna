"""Trusted access to private patient-avatar objects.

Patient avatars live in a private Storage bucket. The database stores only the
stable object path; every outward ``profile_image_url`` is a short-lived signed
URL created after the caller has been authorized by the route that returns the
patient. Signed URLs are never written back to the database.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import unquote

from fastapi import HTTPException

from app.core.storage_access_inventory import (
    IMAGE_EXTENSIONS,
    PATIENT_AVATARS_BUCKET,
    object_path_is_valid,
)
from app.core.supabase_admin import supabase_admin

# Single source of truth for every patient-avatar signed URL issued by the API.
PATIENT_AVATAR_URL_TTL_SECONDS = 60

_LEGACY_PUBLIC_PATH_MARKER = (
    f"/storage/v1/object/public/{PATIENT_AVATARS_BUCKET}/"
)


class PatientAvatarAccessError(RuntimeError):
    """Base class for private avatar access failures."""


class PatientAvatarSigningError(PatientAvatarAccessError):
    """Raised when Storage cannot issue a valid signed URL."""


def is_patient_avatar_object_path(object_path: object, patient_id: object) -> bool:
    """Return whether a path is the exact deterministic patient-owned path."""
    if not isinstance(object_path, str) or not object_path or not patient_id:
        return False
    parts = object_path.split("/")
    if len(parts) != 2 or parts[0] != str(patient_id):
        return False
    if not parts[1].startswith("avatar."):
        return False
    return (
        object_path_is_valid(PATIENT_AVATARS_BUCKET, object_path, patient_id)
        and parts[1].rsplit(".", 1)[-1].lower() in set(IMAGE_EXTENSIONS.values())
    )


def patient_avatar_object_path(
    *,
    patient_id: str,
    stored_path: str | None = None,
    legacy_url: str | None = None,
) -> str | None:
    """Resolve an authorized object path from stable or legacy stored values."""
    if stored_path:
        candidate = str(stored_path).strip()
        return candidate if is_patient_avatar_object_path(candidate, patient_id) else None

    if not legacy_url:
        return None

    value = str(legacy_url).strip()
    marker_index = value.find(_LEGACY_PUBLIC_PATH_MARKER)
    if marker_index >= 0:
        value = value[marker_index + len(_LEGACY_PUBLIC_PATH_MARKER) :]
        value = unquote(value.split("?", 1)[0].split("#", 1)[0]).strip("/")

    return value if is_patient_avatar_object_path(value, patient_id) else None


def create_signed_patient_avatar_url(*, patient_id: str, object_path: str) -> str:
    """Issue a short-lived signed URL for one validated patient-owned object."""
    if not is_patient_avatar_object_path(object_path, patient_id):
        raise PatientAvatarSigningError("invalid patient avatar object path")

    try:
        response = supabase_admin.storage.from_(PATIENT_AVATARS_BUCKET).create_signed_url(
            object_path,
            PATIENT_AVATAR_URL_TTL_SECONDS,
        )
    except Exception as exc:
        raise PatientAvatarSigningError("unable to sign patient avatar") from exc

    signed_url: str | None = None
    if isinstance(response, Mapping):
        candidate = response.get("signedURL") or response.get("signedUrl")
        if isinstance(candidate, str) and candidate:
            signed_url = candidate

    if signed_url is None:
        raise PatientAvatarSigningError("storage returned no signed URL")
    return signed_url


def with_private_avatar_url(patient: Mapping[str, Any]) -> dict[str, Any]:
    """Return an API-safe patient row with an ephemeral avatar URL.

    The stable object path is removed. If no trusted path can be resolved, the
    outward URL is null. If signing fails, the route fails closed with a 500
    rather than exposing a legacy public URL.
    """
    result = dict(patient)
    result.pop("profile_image_path", None)

    patient_id = str(result.get("id") or "")
    object_path = patient_avatar_object_path(
        patient_id=patient_id,
        stored_path=patient.get("profile_image_path"),
        legacy_url=patient.get("profile_image_url"),
    )
    if object_path is None:
        result["profile_image_url"] = None
        return result

    try:
        result["profile_image_url"] = create_signed_patient_avatar_url(
            patient_id=patient_id,
            object_path=object_path,
        )
    except PatientAvatarAccessError as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to issue profile image URL",
        ) from exc
    return result


def with_private_avatar_urls(
    patients: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Apply the same private-avatar projection to a collection of patients."""
    return [with_private_avatar_url(patient) for patient in patients]
