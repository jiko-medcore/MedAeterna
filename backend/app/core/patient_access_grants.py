"""SPEC-06 canonical patient-access grant schema contract.

This is a validation/reference model. It does not create or query a database
table, authorize routes, or replace SPEC-04's relationship evaluator.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.core.patient_relationship_policy import CLINICAL_RESOURCES, RelationshipEvidence


CANONICAL_TABLE = "patient_access_grants"
LEGACY_TABLE = "patient_access"
GRANT_STATUSES = frozenset({"pending", "approved", "revoked", "expired"})
GRANT_AUDIT_ACTIONS = frozenset({"requested", "approved", "revoked", "expired"})


class PatientAccessGrantRecord(BaseModel):
    """Normalized target row for public.patient_access_grants."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    patient_id: UUID
    practitioner_id: UUID
    organization_id: UUID
    access_type: Literal["patient_granted"] = "patient_granted"
    access_level: Literal["read"] = "read"
    resource_families: tuple[str, ...]
    status: Literal["pending", "approved", "revoked", "expired"]
    requested_by: UUID
    requested_at: datetime
    granted_by: UUID | None = None
    granted_at: datetime | None = None
    effective_from: datetime
    expires_at: datetime
    revoked_by: UUID | None = None
    revoked_at: datetime | None = None
    revocation_reason: str | None = None
    expired_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator(
        "requested_at",
        "granted_at",
        "effective_from",
        "expires_at",
        "revoked_at",
        "expired_at",
        "created_at",
        "updated_at",
    )
    @classmethod
    def require_timezone_aware_timestamps(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("grant timestamps must include a timezone")
        return value

    @field_validator("resource_families")
    @classmethod
    def require_explicit_unique_resource_scope(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("at least one clinical resource family is required")
        if len(values) != len(set(values)):
            raise ValueError("resource families must not contain duplicates")
        if not set(values).issubset(CLINICAL_RESOURCES):
            raise ValueError("resource family is not in the SPEC-04 clinical catalogue")
        return values

    @model_validator(mode="after")
    def validate_lifecycle_and_period(self) -> "PatientAccessGrantRecord":
        has_grant_event = self.granted_by is not None and self.granted_at is not None
        partial_grant_event = (self.granted_by is None) != (self.granted_at is None)
        has_revoke_event = self.revoked_by is not None and self.revoked_at is not None
        partial_revoke_event = (self.revoked_by is None) != (self.revoked_at is None)

        if partial_grant_event or partial_revoke_event:
            raise ValueError("grant and revocation actor/timestamp fields must be paired")
        if self.granted_at is not None and self.granted_at < self.requested_at:
            raise ValueError("grant approval cannot predate its request")
        period_start = max(
            self.effective_from,
            self.granted_at or self.requested_at,
        )
        if self.expires_at <= period_start:
            raise ValueError("grant expiry must follow approval and effective start")
        if self.revoked_at is not None:
            revoke_floor = self.granted_at or self.requested_at
            if self.revoked_at < revoke_floor:
                raise ValueError("revocation cannot predate the request or approval")
        if self.status == "pending" and (has_grant_event or has_revoke_event):
            raise ValueError("pending grants cannot contain approval or revocation events")
        if self.status == "pending" and self.expired_at is not None:
            raise ValueError("pending grants cannot contain an expiry event")
        if self.status == "approved" and (
            not has_grant_event or has_revoke_event or self.expired_at is not None
        ):
            raise ValueError("approved grants require a grantor and cannot be revoked")
        if self.status == "revoked" and not has_revoke_event:
            raise ValueError("revoked grants require a revoker and revocation timestamp")
        if self.status == "revoked" and self.expired_at is not None:
            raise ValueError("revoked grants cannot also be marked expired")
        if self.status == "expired":
            if self.expired_at is None or has_revoke_event:
                raise ValueError("expired grants require an expiry event and cannot be revoked")
            if self.expired_at < self.expires_at:
                raise ValueError("expiry event cannot predate the grant expiry")
        return self

    def as_relationship_evidence(self, *, source_verified: bool = False) -> RelationshipEvidence:
        """Map the row to SPEC-04's normalized grant evidence.

        The caller may set source_verified only after loading and validating the
        row through a trusted backend path. This method never asserts that fact.
        """
        return RelationshipEvidence(
            kind="patient_grant",
            status=self.status,
            patient_id=str(self.patient_id),
            practitioner_id=str(self.practitioner_id),
            organization_id=str(self.organization_id),
            effective_from=max(
                self.effective_from,
                self.granted_at or self.requested_at,
            ),
            effective_until=self.expires_at,
            resource_families=frozenset(self.resource_families),
            actions=frozenset({"read"}),
            source_verified=source_verified,
        )


def can_transition_grant_status(
    *,
    current_status: str,
    next_status: str,
    actor_user_id: UUID | str | None,
    patient_user_id: UUID | str | None,
    requester_user_id: UUID | str | None,
) -> bool:
    """Return whether the verified actor may make a grant lifecycle change.

    Identity links must be resolved by trusted server code before calling this
    function. Pending requests may be cancelled by the requester; only the
    patient may approve a request or revoke an approved grant.
    """
    if current_status not in GRANT_STATUSES or next_status not in GRANT_STATUSES:
        return False
    if actor_user_id is None or patient_user_id is None:
        return False

    actor = str(actor_user_id)
    is_patient = actor == str(patient_user_id)
    is_requester = requester_user_id is not None and actor == str(requester_user_id)

    if current_status == "pending" and next_status == "approved":
        return is_patient
    if current_status == "pending" and next_status == "revoked":
        return is_patient or is_requester
    if current_status == "approved" and next_status == "revoked":
        return is_patient
    return False


def can_mark_grant_expired(
    *,
    current_status: str,
    expires_at: datetime | None,
    now: datetime,
) -> bool:
    """Permit a trusted expiry worker to close an elapsed pending/approved row."""
    return (
        current_status in {"pending", "approved"}
        and isinstance(expires_at, datetime)
        and expires_at.tzinfo is not None
        and expires_at.utcoffset() is not None
        and isinstance(now, datetime)
        and now.tzinfo is not None
        and now.utcoffset() is not None
        and now >= expires_at
    )
