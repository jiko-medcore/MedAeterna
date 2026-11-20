"""SPEC-12 reference inventory for storage buckets and object access.

This is a declarative model of the *intended* storage boundary. It does not
create buckets, call the Storage API, or prove that the deployed project matches
the model. Migrations and catalog tests must compare the live project against
these expectations.

Client roles retain the platform-managed grants on ``storage.objects`` and
``storage.buckets``; those ACL entries are owned by ``supabase_storage_admin``
and cannot be revoked by an application migration. Effective denial is provided
by an explicit ``FOR ALL ... USING (false) WITH CHECK (false)`` policy for
``anon`` and ``authenticated``. Public retrieval is provided by the bucket's
``public`` flag and is unaffected by that policy. Every mutation goes through
the trusted backend with the SPEC-10 service-role evidence. Private objects,
when introduced, must be read through short-lived signed URLs issued by that
same trusted path.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable, Mapping

from app.core.database_execution_policy import ExecutionMode


class BucketClass(StrEnum):
    PUBLIC_OWNED = "public_owned"
    PRIVATE_OWNED = "private_owned"


@dataclass(frozen=True)
class StoragePolicyRule:
    """An explicit ``storage.objects`` RLS policy expected in the catalog."""

    name: str
    command: str
    role: str
    predicate: str
    check: str | None = None


@dataclass(frozen=True)
class BucketAccessRule:
    name: str
    classification: BucketClass
    public: bool
    file_size_limit: int
    allowed_mime_types: frozenset[str]
    extension_by_mime: Mapping[str, str]
    owner_token: str
    object_path_pattern: str
    execution_mode: ExecutionMode
    note: str = ""


IMAGE_SIGNATURES: Mapping[str, tuple[tuple[int, bytes], ...]] = {
    "image/png": ((0, b"\x89PNG\r\n\x1a\n"),),
    "image/jpeg": ((0, b"\xff\xd8\xff"),),
    "image/webp": ((0, b"RIFF"), (8, b"WEBP")),
}

IMAGE_EXTENSIONS: Mapping[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

MAX_IMAGE_SIZE_BYTES = 2 * 1024 * 1024

CLIENT_DENY_POLICY = StoragePolicyRule(
    name="Deny direct client object access",
    command="ALL",
    role="anon, authenticated",
    predicate="false",
    check="false",
)
STORAGE_OBJECT_POLICIES: tuple[StoragePolicyRule, ...] = (CLIENT_DENY_POLICY,)

ORGANIZATION_LOGOS_BUCKET = "organization-logos"
PATIENT_AVATARS_BUCKET = "patient-avatars"
PRACTITIONER_PHOTOS_BUCKET = "practitioner-photos"


def _bucket(
    name: str,
    *,
    classification: BucketClass,
    public: bool,
    note: str,
    owner_token: str,
    object_path_pattern: str,
) -> BucketAccessRule:
    return BucketAccessRule(
        name=name,
        classification=classification,
        public=public,
        file_size_limit=MAX_IMAGE_SIZE_BYTES,
        allowed_mime_types=frozenset(IMAGE_EXTENSIONS),
        extension_by_mime=dict(IMAGE_EXTENSIONS),
        owner_token=owner_token,
        object_path_pattern=object_path_pattern,
        execution_mode=ExecutionMode.SERVICE_ROLE,
        note=note,
    )


# The buckets that are installed by the SPEC-12 migration. A bucket that is not
# registered here receives no configuration, no grant, and no policy from this
# model.
STORAGE_BUCKET_INVENTORY: dict[str, BucketAccessRule] = {
    ORGANIZATION_LOGOS_BUCKET: _bucket(
        ORGANIZATION_LOGOS_BUCKET,
        classification=BucketClass.PUBLIC_OWNED,
        public=True,
        owner_token="organization id",
        object_path_pattern="<organization_id>/logo.<ext>",
        note="Public branding asset. Writes require scoped organization-admin evidence.",
    ),
    PATIENT_AVATARS_BUCKET: _bucket(
        PATIENT_AVATARS_BUCKET,
        classification=BucketClass.PUBLIC_OWNED,
        public=True,
        owner_token="patient user id",
        object_path_pattern="<patient_id>/avatar.<ext>",
        note=(
            "Public non-clinical profile image, consistent with the existing profile "
            "URL contract. Writes require verified patient self-service evidence."
        ),
    ),
    PRACTITIONER_PHOTOS_BUCKET: _bucket(
        PRACTITIONER_PHOTOS_BUCKET,
        classification=BucketClass.PUBLIC_OWNED,
        public=True,
        owner_token="practitioner id",
        object_path_pattern="<practitioner_id>/photo.<ext>",
        note=(
            "Public directory photo. Installed with limits now; no backend upload "
            "route exists yet, so a future route must use the trusted path."
        ),
    ),
}

# Buckets required by the target model that are not installed. Their creation
# migration must add them to STORAGE_BUCKET_INVENTORY in the same change.
PLANNED_BUCKETS: tuple[str, ...] = ("patient-documents",)


def bucket_is_covered(name: str) -> bool:
    """Return whether a bucket has a reviewed access rule."""
    return name in STORAGE_BUCKET_INVENTORY


def expected_bucket_config(name: str) -> tuple[bool, int, frozenset[str]] | None:
    """Return the expected bucket configuration for comparison with the catalog."""
    rule = STORAGE_BUCKET_INVENTORY.get(name)
    if rule is None:
        return None
    return rule.public, rule.file_size_limit, rule.allowed_mime_types


def all_policy_names() -> tuple[str, ...]:
    return tuple(policy.name for policy in STORAGE_OBJECT_POLICIES)


def policy_violations(actual_policy_names: Iterable[str]) -> list[str]:
    """Report policies that create an access path outside the reviewed model."""
    allowed = set(all_policy_names())
    return sorted(set(actual_policy_names) - allowed)


def missing_policy_violations(actual_policy_names: Iterable[str]) -> list[str]:
    """Report reviewed policies that are absent from the catalog."""
    actual = set(actual_policy_names)
    return sorted(set(all_policy_names()) - actual)


def object_owner_token(object_name: str) -> str | None:
    """Return the first path token, which must encode the owning principal."""
    parts = [part for part in object_name.split("/") if part]
    return parts[0] if parts else None


def object_path_is_valid(bucket: str, object_name: str, owner_id: object) -> bool:
    """Validate the deterministic owner-scoped path used by trusted writers."""
    rule = STORAGE_BUCKET_INVENTORY.get(bucket)
    if rule is None or not owner_id:
        return False
    if object_owner_token(object_name) != str(owner_id):
        return False
    extension = object_name.rsplit(".", 1)[-1].lower() if "." in object_name else ""
    return extension in set(rule.extension_by_mime.values())
