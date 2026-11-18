from datetime import datetime, timedelta, timezone

import pytest

from app.core.patient_relationship_policy import (
    CLINICAL_ACTIONS,
    CLINICAL_RESOURCES,
    RelationshipEvidence,
    evaluate_patient_relationship,
)
from app.core.role_catalogue import ORGANIZATION_ADMINISTRATOR, PATIENT, PRACTITIONER, SYSTEM_ADMINISTRATOR


NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)


def evidence(kind="active_treatment", **overrides):
    values = {
        "kind": kind,
        "status": "active" if kind != "patient_grant" else "approved",
        "patient_id": "patient-1",
        "practitioner_id": "practitioner-1",
        "organization_id": "org-1",
        "source_verified": True,
    }
    values.update(overrides)
    return RelationshipEvidence(**values)


def decide(**overrides):
    values = {
        "actor_user_id": "user-1",
        "actor_category": PRACTITIONER,
        "actor_practitioner_id": "practitioner-1",
        "linked_practitioner_user_id": "user-1",
        "patient_id": "patient-1",
        "organization_id": "org-1",
        "resource_family": "observation",
        "action": "read",
        "evidence": [evidence()],
        "now": NOW,
    }
    values.update(overrides)
    return evaluate_patient_relationship(**values)


def test_every_clinical_resource_and_supported_action_has_expected_relationship_gate():
    for resource in CLINICAL_RESOURCES:
        for action in CLINICAL_ACTIONS:
            active_assignment = decide(resource_family=resource, action=action)
            if resource == "lab_result" and action in {"create", "update"}:
                assert active_assignment.decision == "deny"
                order_assignment = evidence(
                    "lab_order_assignment", resource_id="order-1"
                )
                result = decide(
                    resource_family=resource,
                    action=action,
                    resource_id="order-1",
                    evidence=[order_assignment],
                )
                assert result.allowed
            else:
                assert active_assignment.allowed, (resource, action, active_assignment)


def test_patient_can_read_only_their_own_permitted_clinical_resource_families():
    for resource in CLINICAL_RESOURCES:
        own = decide(
            actor_category=PATIENT,
            actor_patient_id="patient-1",
            actor_practitioner_id=None,
            linked_practitioner_user_id=None,
            resource_family=resource,
            action="read",
            evidence=[],
        )
        assert own.allowed
        other = decide(
            actor_category=PATIENT,
            actor_patient_id="patient-2",
            actor_practitioner_id=None,
            linked_practitioner_user_id=None,
            resource_family=resource,
            action="read",
            evidence=[],
        )
        assert other.decision == "deny"

        for action in {"create", "update"}:
            cannot_write = decide(
                actor_category=PATIENT,
                actor_patient_id="patient-1",
                resource_family=resource,
                action=action,
                evidence=[],
            )
            assert cannot_write.decision == "deny"

    no_organization_needed_for_patient_self_read = decide(
        actor_category=PATIENT,
        actor_patient_id="patient-1",
        actor_practitioner_id=None,
        linked_practitioner_user_id=None,
        organization_id=None,
        resource_family="clinical_history",
        action="read",
        evidence=[],
    )
    assert no_organization_needed_for_patient_self_read.allowed


def test_scoped_patient_grant_allows_only_approved_read_for_its_scope():
    grant = evidence(
        "patient_grant",
        resource_families=frozenset({"observation", "lab_result"}),
        actions=frozenset({"read"}),
        effective_from=NOW - timedelta(days=1),
        effective_until=NOW + timedelta(days=1),
    )
    assert decide(evidence=[grant], resource_family="observation").allowed
    assert decide(evidence=[grant], resource_family="condition").decision == "deny"
    assert decide(evidence=[grant], action="update").decision == "deny"
    assert decide(evidence=[grant], action="create").decision == "deny"


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "pending"},
        {"status": "revoked"},
        {"effective_from": NOW + timedelta(seconds=1)},
        {"effective_until": NOW},
        {"source_verified": False},
        {"patient_id": "patient-2"},
        {"practitioner_id": "practitioner-2"},
        {"organization_id": "org-2"},
        {"resource_families": frozenset()},
        {"actions": frozenset()},
    ],
)
def test_patient_grant_requires_approved_current_exactly_scoped_evidence(overrides):
    base = {
        "resource_families": frozenset({"observation"}),
        "actions": frozenset({"read"}),
    }
    base.update(overrides)
    grant = evidence("patient_grant", **base)
    assert decide(evidence=[grant]).decision == "deny"


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "revoked"},
        {"status": "pending"},
        {"effective_from": NOW + timedelta(minutes=1)},
        {"effective_until": NOW},
        {"source_verified": False},
        {"patient_id": "patient-2"},
        {"practitioner_id": "practitioner-2"},
        {"organization_id": "org-2"},
    ],
)
def test_inactive_unverified_or_mismatched_assignment_denies(overrides):
    assert decide(evidence=[evidence(**overrides)]).decision == "deny"


def test_organization_membership_and_emergency_relationships_do_not_authorize():
    membership = evidence("organization_membership")
    emergency = evidence("emergency")
    assert decide(evidence=[]).decision == "deny"
    assert decide(evidence=[membership]).decision == "deny"
    assert decide(evidence=[emergency]).decision == "deny"


def test_lab_result_writes_require_the_exact_active_order_assignment():
    order = evidence("lab_order_assignment", resource_id="order-1")
    assert decide(
        resource_family="lab_result",
        action="create",
        resource_id="order-1",
        evidence=[order],
    ).allowed
    assert decide(
        resource_family="lab_result",
        action="update",
        resource_id="order-2",
        evidence=[order],
    ).decision == "deny"
    assert decide(
        resource_family="observation",
        action="update",
        resource_id="order-1",
        evidence=[order],
    ).decision == "deny"
    assert decide(
        resource_family="lab_result",
        action="delete",
        resource_id="order-1",
        evidence=[order],
    ).decision == "deny"


@pytest.mark.parametrize("category", [ORGANIZATION_ADMINISTRATOR, SYSTEM_ADMINISTRATOR, "unmapped"])
def test_non_care_roles_do_not_gain_patient_relationship_from_platform_or_org_role(category):
    assert decide(actor_category=category).decision == "deny"


def test_practitioner_profile_must_be_linked_to_authenticated_user():
    assert decide(linked_practitioner_user_id="someone-else").decision == "deny"
    assert decide(actor_practitioner_id=None).decision == "deny"


def test_missing_identity_scope_and_timezone_are_denied():
    assert decide(actor_user_id=None).decision == "deny"
    assert decide(patient_id=None).decision == "deny"
    assert decide(organization_id=None).decision == "deny"
    assert decide(now=NOW.replace(tzinfo=None)).decision == "deny"


def test_unknown_resource_and_non_clinical_actions_are_denied():
    assert decide(resource_family="unknown").decision == "deny"
    assert decide(action="delete").decision == "deny"
    assert decide(action="administer").decision == "deny"
    assert decide(action="retry").decision == "deny"


def test_another_evidence_path_may_allow_without_masking_wrong_org():
    unrelated = evidence(organization_id="org-2")
    valid = evidence("patient_grant", resource_families=frozenset({"observation"}), actions=frozenset({"read"}))
    assert decide(evidence=[unrelated, valid]).allowed
    assert decide(organization_id="org-2", evidence=[valid]).decision == "deny"
