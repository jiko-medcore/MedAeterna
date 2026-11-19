from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.core.patient_access_grants import (
    CANONICAL_TABLE,
    GRANT_AUDIT_ACTIONS,
    PatientAccessGrantRecord,
    can_mark_grant_expired,
    can_transition_grant_status,
)
from app.core.patient_relationship_policy import evaluate_patient_relationship
from app.core.role_catalogue import PRACTITIONER


NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
PATIENT = UUID("00000000-0000-0000-0000-000000000001")
PRACTITIONER_ID = UUID("00000000-0000-0000-0000-000000000002")
ORG = UUID("00000000-0000-0000-0000-000000000003")
PATIENT_USER = UUID("00000000-0000-0000-0000-000000000001")
REQUESTER = UUID("00000000-0000-0000-0000-000000000004")


def record(**overrides):
    values = {
        "id": UUID("00000000-0000-0000-0000-000000000010"),
        "patient_id": PATIENT,
        "practitioner_id": PRACTITIONER_ID,
        "organization_id": ORG,
        "access_type": "patient_granted",
        "access_level": "read",
        "resource_families": ("observation", "encounter"),
        "status": "approved",
        "requested_by": REQUESTER,
        "requested_at": NOW - timedelta(days=2),
        "granted_by": PATIENT_USER,
        "granted_at": NOW - timedelta(days=1),
        "effective_from": NOW - timedelta(days=1),
        "expires_at": NOW + timedelta(days=1),
        "created_at": NOW - timedelta(days=2),
        "updated_at": NOW - timedelta(days=1),
    }
    values.update(overrides)
    return PatientAccessGrantRecord(**values)


def test_canonical_table_contract_has_one_scoped_patient_grant_type():
    assert CANONICAL_TABLE == "patient_access_grants"
    assert GRANT_AUDIT_ACTIONS == {"requested", "approved", "revoked", "expired"}
    grant = record()
    assert grant.access_type == "patient_granted"
    assert grant.access_level == "read"
    assert set(grant.resource_families) == {"observation", "encounter"}


@pytest.mark.parametrize(
    "overrides",
    [
        {"access_type": "assigned"},
        {"access_type": "emergency"},
        {"access_level": "write"},
        {"access_level": "full"},
        {"resource_families": ()},
        {"resource_families": ("observation", "observation")},
        {"resource_families": ("unknown_resource",)},
        {"expires_at": None},
        {"expires_at": NOW - timedelta(days=1)},
        {"effective_from": NOW.replace(tzinfo=None)},
        {"expires_at": NOW.replace(tzinfo=None)},
        {"granted_at": NOW.replace(tzinfo=None)},
        {"granted_at": NOW + timedelta(days=1)},
        {"status": "active"},
    ],
)
def test_schema_contract_rejects_unsupported_scope_and_invalid_periods(overrides):
    with pytest.raises(ValidationError):
        record(**overrides)


def test_status_rows_require_consistent_approval_and_revocation_events():
    pending = record(
        status="pending",
        granted_by=None,
        granted_at=None,
    )
    assert pending.status == "pending"

    revoked_approved = record(
        status="revoked",
        revoked_by=PATIENT_USER,
        revoked_at=NOW,
        revocation_reason="Patient withdrew access",
    )
    assert revoked_approved.status == "revoked"

    expired_approved = record(
        status="expired",
        expires_at=NOW - timedelta(seconds=1),
        expired_at=NOW,
        updated_at=NOW,
    )
    assert expired_approved.status == "expired"

    invalid = [
        {"status": "pending"},
        {"status": "approved", "granted_by": None},
        {"status": "approved", "granted_at": None},
        {"status": "revoked"},
        {"status": "revoked", "revoked_by": PATIENT_USER},
        {"status": "revoked", "revoked_at": NOW},
        {"status": "revoked", "revoked_by": PATIENT_USER, "revoked_at": NOW - timedelta(days=3)},
        {"status": "expired"},
        {"status": "expired", "expired_at": NOW},
    ]
    for overrides in invalid:
        with pytest.raises(ValidationError):
            record(**overrides)


def test_only_patient_approves_and_revokes_approved_grants():
    assert can_transition_grant_status(
        current_status="pending",
        next_status="approved",
        actor_user_id=PATIENT_USER,
        patient_user_id=PATIENT_USER,
        requester_user_id=REQUESTER,
    )
    assert not can_transition_grant_status(
        current_status="pending",
        next_status="approved",
        actor_user_id=REQUESTER,
        patient_user_id=PATIENT_USER,
        requester_user_id=REQUESTER,
    )
    assert can_transition_grant_status(
        current_status="approved",
        next_status="revoked",
        actor_user_id=PATIENT_USER,
        patient_user_id=PATIENT_USER,
        requester_user_id=REQUESTER,
    )
    assert not can_transition_grant_status(
        current_status="approved",
        next_status="revoked",
        actor_user_id=REQUESTER,
        patient_user_id=PATIENT_USER,
        requester_user_id=REQUESTER,
    )


def test_pending_request_can_be_cancelled_by_requester_or_patient():
    for actor in (REQUESTER, PATIENT_USER):
        assert can_transition_grant_status(
            current_status="pending",
            next_status="revoked",
            actor_user_id=actor,
            patient_user_id=PATIENT_USER,
            requester_user_id=REQUESTER,
        )


def test_only_expiry_worker_may_mark_pending_or_approved_after_expiry():
    past = NOW - timedelta(seconds=1)
    future = NOW + timedelta(seconds=1)
    assert can_mark_grant_expired(current_status="pending", expires_at=past, now=NOW)
    assert can_mark_grant_expired(current_status="approved", expires_at=past, now=NOW)
    assert not can_mark_grant_expired(current_status="approved", expires_at=future, now=NOW)
    assert not can_mark_grant_expired(current_status="revoked", expires_at=past, now=NOW)
    assert not can_mark_grant_expired(current_status="expired", expires_at=past, now=NOW)


@pytest.mark.parametrize(
    "current,next_status,actor",
    [
        ("revoked", "approved", PATIENT_USER),
        ("revoked", "pending", PATIENT_USER),
        ("approved", "pending", PATIENT_USER),
        ("approved", "expired", PATIENT_USER),
        ("pending", "pending", PATIENT_USER),
        ("pending", "revoked", UUID("00000000-0000-0000-0000-000000000099")),
        ("unknown", "approved", PATIENT_USER),
    ],
)
def test_illegal_or_unauthorized_state_transitions_deny(current, next_status, actor):
    assert not can_transition_grant_status(
        current_status=current,
        next_status=next_status,
        actor_user_id=actor,
        patient_user_id=PATIENT_USER,
        requester_user_id=REQUESTER,
    )


def test_patient_grant_contract_maps_to_spec04_read_only_evidence():
    grant = record()
    evidence = grant.as_relationship_evidence(source_verified=True)

    read = evaluate_patient_relationship(
        actor_user_id=str(PRACTITIONER_ID),
        actor_category=PRACTITIONER,
        actor_practitioner_id=str(PRACTITIONER_ID),
        linked_practitioner_user_id=str(PRACTITIONER_ID),
        patient_id=str(PATIENT),
        organization_id=str(ORG),
        resource_family="observation",
        action="read",
        evidence=[evidence],
        now=NOW,
    )
    assert read.allowed

    for resource, action in (("condition", "read"), ("observation", "update")):
        denied = evaluate_patient_relationship(
            actor_user_id=str(PRACTITIONER_ID),
            actor_category=PRACTITIONER,
            actor_practitioner_id=str(PRACTITIONER_ID),
            linked_practitioner_user_id=str(PRACTITIONER_ID),
            patient_id=str(PATIENT),
            organization_id=str(ORG),
            resource_family=resource,
            action=action,
            evidence=[evidence],
            now=NOW,
        )
        assert denied.decision == "deny"

    pending_evidence = record(
        status="pending",
        granted_by=None,
        granted_at=None,
    ).as_relationship_evidence(source_verified=True)
    pending = evaluate_patient_relationship(
        actor_user_id=str(PRACTITIONER_ID),
        actor_category=PRACTITIONER,
        actor_practitioner_id=str(PRACTITIONER_ID),
        linked_practitioner_user_id=str(PRACTITIONER_ID),
        patient_id=str(PATIENT),
        organization_id=str(ORG),
        resource_family="observation",
        action="read",
        evidence=[pending_evidence],
        now=NOW,
    )
    assert pending.decision == "deny"


def test_untrusted_or_expired_canonical_grant_evidence_denies():
    grant = record()
    untrusted = grant.as_relationship_evidence()
    expired = record(
        expires_at=NOW - timedelta(seconds=1),
        updated_at=NOW,
    ).as_relationship_evidence(source_verified=True)

    for evidence in (untrusted, expired):
        decision = evaluate_patient_relationship(
            actor_user_id=str(PRACTITIONER_ID),
            actor_category=PRACTITIONER,
            actor_practitioner_id=str(PRACTITIONER_ID),
            linked_practitioner_user_id=str(PRACTITIONER_ID),
            patient_id=str(PATIENT),
            organization_id=str(ORG),
            resource_family="observation",
            action="read",
            evidence=[evidence],
            now=NOW,
        )
        assert decision.decision == "deny"
