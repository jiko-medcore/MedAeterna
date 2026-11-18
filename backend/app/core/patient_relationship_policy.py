"""SPEC-04 patient-to-practitioner relationship policy reference.

The evaluator consumes relationship evidence already resolved by trusted
backend code. It does not query a database or make a route secure by itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

from app.core.role_catalogue import ORGANIZATION_ADMINISTRATOR, PATIENT, PRACTITIONER, SYSTEM_ADMINISTRATOR


CLINICAL_RESOURCES = frozenset(
    {
        "clinical_history",
        "encounter",
        "observation",
        "condition",
        "prescription",
        "lab_result",
        "clinical_document",
    }
)
CLINICAL_ACTIONS = frozenset({"read", "create", "update"})


@dataclass(frozen=True)
class RelationshipEvidence:
    """Normalized, trusted relationship evidence from an approved source."""

    kind: str
    status: str
    patient_id: str
    organization_id: str
    practitioner_id: str | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    resource_families: frozenset[str] = field(default_factory=frozenset)
    actions: frozenset[str] = field(default_factory=frozenset)
    resource_id: str | None = None
    source_verified: bool = False


@dataclass(frozen=True)
class RelationshipDecision:
    decision: str
    reason: str

    @property
    def allowed(self) -> bool:
        return self.decision == "allow"


def _same_id(left: str | None, right: str | None) -> bool:
    return (
        left is not None
        and right is not None
        and bool(str(left).strip())
        and bool(str(right).strip())
        and str(left).strip() == str(right).strip()
    )


def _effective_at(
    *,
    status: str,
    effective_from: datetime | None,
    effective_until: datetime | None,
    now: datetime,
    expected_status: str,
) -> bool:
    if (
        status != expected_status
        or not isinstance(now, datetime)
        or now.tzinfo is None
        or now.utcoffset() is None
    ):
        return False
    for boundary in (effective_from, effective_until):
        if boundary is not None and (
            not isinstance(boundary, datetime)
            or boundary.tzinfo is None
            or boundary.utcoffset() is None
        ):
            return False
    if effective_from is not None and now < effective_from:
        return False
    if effective_until is not None and now >= effective_until:
        return False
    return True


def evaluate_patient_relationship(
    *,
    actor_user_id: str | None,
    actor_category: str,
    actor_patient_id: str | None = None,
    actor_practitioner_id: str | None = None,
    linked_practitioner_user_id: str | None = None,
    patient_id: str | None,
    organization_id: str | None,
    resource_family: str,
    action: str,
    evidence: Iterable[RelationshipEvidence] = (),
    resource_id: str | None = None,
    now: datetime,
) -> RelationshipDecision:
    """Fail-closed SPEC-04 relationship decision for a clinical resource.

    This answers only whether the caller has a qualifying patient relationship.
    SPEC-03 role/action permission, SPEC-05 consent, workflow, field filtering,
    authentication, and database/RLS controls must still pass independently.
    """
    if actor_user_id is None or not str(actor_user_id).strip():
        return RelationshipDecision("deny", "authenticated actor identity is required")
    if patient_id is None or not str(patient_id).strip():
        return RelationshipDecision("deny", "patient context is required")
    if not isinstance(actor_category, str):
        return RelationshipDecision("deny", "role category is invalid")

    resource = resource_family.strip().casefold() if isinstance(resource_family, str) else ""
    operation = action.strip().casefold() if isinstance(action, str) else ""
    if resource not in CLINICAL_RESOURCES or operation not in CLINICAL_ACTIONS:
        return RelationshipDecision("deny", "resource or action is outside SPEC-04 scope")

    if actor_category == PATIENT:
        if operation != "read":
            return RelationshipDecision("deny", "patients have no clinical write relationship")
        if _same_id(actor_patient_id, patient_id):
            return RelationshipDecision("allow", "patient is the authenticated subject")
        return RelationshipDecision("deny", "patient may read only their own clinical resources")

    if actor_category != PRACTITIONER:
        if actor_category in {ORGANIZATION_ADMINISTRATOR, SYSTEM_ADMINISTRATOR}:
            return RelationshipDecision("deny", "administrative role is not a patient-care relationship")
        return RelationshipDecision("deny", "role category is not authorized for patient relationships")

    if actor_practitioner_id is None:
        return RelationshipDecision("deny", "practitioner identity is not verified")
    if not _same_id(actor_user_id, linked_practitioner_user_id):
        return RelationshipDecision("deny", "practitioner profile is not linked to the authenticated actor")
    if organization_id is None or not str(organization_id).strip():
        return RelationshipDecision("deny", "practitioner organization context is required")
    if (
        not isinstance(now, datetime)
        or now.tzinfo is None
        or now.utcoffset() is None
    ):
        return RelationshipDecision("deny", "decision time must include a timezone")

    try:
        relationship_evidence = tuple(evidence)
    except TypeError:
        return RelationshipDecision("deny", "relationship evidence is invalid")

    for relationship in relationship_evidence:
        if not isinstance(relationship, RelationshipEvidence):
            continue
        if not relationship.source_verified:
            continue
        if not _same_id(relationship.patient_id, patient_id):
            continue
        if not _same_id(relationship.organization_id, organization_id):
            continue
        if not _same_id(relationship.practitioner_id, actor_practitioner_id):
            continue

        if relationship.kind == "active_treatment":
            if not _effective_at(
                status=relationship.status,
                effective_from=relationship.effective_from,
                effective_until=relationship.effective_until,
                now=now,
                expected_status="active",
            ):
                continue
            if resource == "lab_result" and operation in {"create", "update"}:
                continue
            return RelationshipDecision("allow", "active treatment assignment matches patient and organization")

        if relationship.kind == "patient_grant":
            if operation != "read":
                continue
            if not _effective_at(
                status=relationship.status,
                effective_from=relationship.effective_from,
                effective_until=relationship.effective_until,
                now=now,
                expected_status="approved",
            ):
                continue
            if resource not in relationship.resource_families or operation not in relationship.actions:
                continue
            return RelationshipDecision("allow", "approved patient grant covers this read resource")

        if relationship.kind == "lab_order_assignment":
            if resource != "lab_result" or operation not in {"create", "update"}:
                continue
            if not _same_id(relationship.resource_id, resource_id):
                continue
            if not _effective_at(
                status=relationship.status,
                effective_from=relationship.effective_from,
                effective_until=relationship.effective_until,
                now=now,
                expected_status="active",
            ):
                continue
            return RelationshipDecision("allow", "active assignment is bound to this laboratory order")

    return RelationshipDecision("deny", "no active relationship matches the patient, organization, resource, and action")
