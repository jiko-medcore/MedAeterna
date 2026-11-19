from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.core.consent_policy import (
    ACCESS_ACTIONS,
    CLINICAL_ACTIONS,
    CLINICAL_RESOURCES,
    ConsentEvidence,
    ConsentRequirement,
    evaluate_consent,
)
from app.core.role_catalogue import ORGANIZATION_ADMINISTRATOR, PATIENT, PRACTITIONER, SYSTEM_ADMINISTRATOR


NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)


def requirement(**overrides):
    values = {
        "required": True,
        "policy_id": "consent-treatment-v1",
        "purpose": "treatment",
        "allowed_consent_types": frozenset({"treatment"}),
        "source_verified": True,
    }
    values.update(overrides)
    return ConsentRequirement(**values)


def consent(**overrides):
    values = {
        "consent_id": "consent-1",
        "status": "active",
        "patient_id": "patient-1",
        "organization_id": "org-1",
        "practitioner_id": "practitioner-1",
        "recipient_kind": "practitioner",
        "consent_type": "treatment",
        "access_level": "read",
        "purpose_of_use": "treatment",
        "resource_families": frozenset({"observation"}),
        "granted_at": NOW - timedelta(days=1),
        "effective_from": NOW - timedelta(hours=1),
        "expires_at": NOW + timedelta(days=1),
        "decision_authority_verified": True,
        "source_verified": True,
    }
    values.update(overrides)
    return ConsentEvidence(**values)


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
        "requirement": requirement(),
        "evidence": [consent()],
        "now": NOW,
    }
    values.update(overrides)
    return evaluate_consent(**values)


def test_valid_consent_must_match_subject_recipient_org_resource_purpose_and_action():
    result = decide()
    assert result.allowed
    assert result.consent_id == "consent-1"


def test_consent_access_levels_map_to_actions_without_granting_delete_or_admin():
    assert ACCESS_ACTIONS == {
        "read": frozenset({"read"}),
        "write": frozenset({"create", "update"}),
        "full": frozenset({"read", "create", "update"}),
    }
    assert decide(action="update").decision == "deny"
    write = consent(access_level="write")
    assert decide(action="create", evidence=[write]).allowed
    assert decide(action="update", evidence=[write]).allowed
    assert decide(action="read", evidence=[write]).decision == "deny"
    full = consent(access_level="full")
    for action in CLINICAL_ACTIONS:
        assert decide(action=action, evidence=[full]).allowed
    for action in {"delete", "administer", "retry"}:
        assert decide(action=action, evidence=[full]).decision == "deny"


@pytest.mark.parametrize(
    "overrides,request_overrides",
    [
        ({"patient_id": "patient-2"}, {}),
        ({"organization_id": "org-2"}, {}),
        ({"practitioner_id": "practitioner-2"}, {}),
        ({"purpose_of_use": "research"}, {}),
        ({"resource_families": frozenset({"condition"})}, {}),
        ({"consent_type": "research"}, {}),
        ({"status": "draft"}, {}),
        ({"status": "pending"}, {}),
        ({"status": "rejected"}, {}),
        ({"status": "expired"}, {}),
        ({"status": "revoked", "revoked_at": NOW - timedelta(minutes=1)}, {}),
        ({"emergency_access": True}, {}),
        ({"consent_type": "emergency"}, {}),
        ({"source_verified": False}, {}),
        ({"decision_authority_verified": False}, {}),
        ({"expires_at": None}, {}),
        ({"granted_at": None}, {}),
        ({"expires_at": NOW.replace(tzinfo=None)}, {}),
        ({"effective_from": NOW + timedelta(minutes=1)}, {}),
        ({"granted_at": NOW + timedelta(minutes=1)}, {}),
        ({"expires_at": NOW}, {}),
        ({"revoked_at": NOW - timedelta(minutes=1)}, {}),
        ({}, {"resource_family": "condition"}),
        ({}, {"patient_id": "patient-2"}),
        ({}, {"organization_id": "org-2"}),
        ({}, {"actor_practitioner_id": "practitioner-2"}),
    ],
)
def test_mismatched_inactive_unverified_or_out_of_period_consent_denies(
    overrides, request_overrides
):
    assert decide(evidence=[consent(**overrides)], **request_overrides).decision == "deny"


def test_organization_recipient_requires_an_explicit_organization_scope():
    org_consent = consent(
        practitioner_id=None,
        recipient_kind="organization",
    )
    assert decide(evidence=[org_consent]).allowed
    assert decide(organization_id="org-2", evidence=[org_consent]).decision == "deny"

    ambiguous_wildcard = consent(practitioner_id=None, recipient_kind="practitioner")
    assert decide(evidence=[ambiguous_wildcard]).decision == "deny"


def test_non_consent_requirement_passes_only_from_verified_policy():
    not_required = requirement(required=False, allowed_consent_types=frozenset())
    assert decide(requirement=not_required, evidence=[]).allowed
    assert decide(
        requirement=replace(not_required, source_verified=False), evidence=[]
    ).decision == "deny"
    assert decide(requirement=replace(not_required, policy_id=None), evidence=[]).decision == "deny"
    assert decide(requirement=replace(not_required, purpose=None), evidence=[]).decision == "deny"


def test_unknown_requirement_and_unmapped_purpose_policy_fail_closed():
    assert decide(requirement=replace(requirement(), required=None)).decision == "deny"
    assert decide(requirement=replace(requirement(), required=1)).decision == "deny"
    assert decide(
        requirement=replace(requirement(), allowed_consent_types=frozenset({"emergency"}))
    ).decision == "deny"


def test_consent_type_and_purpose_must_both_be_approved_by_policy():
    research_policy = requirement(
        policy_id="consent-research-v1",
        purpose="research",
        allowed_consent_types=frozenset({"research"}),
    )
    research_consent = consent(
        consent_type="research",
        purpose_of_use="research",
    )
    assert decide(requirement=research_policy, evidence=[research_consent]).allowed
    assert decide(requirement=research_policy, evidence=[consent()]).decision == "deny"


@pytest.mark.parametrize(
    "category", [PATIENT, ORGANIZATION_ADMINISTRATOR, SYSTEM_ADMINISTRATOR, "unmapped"]
)
def test_consent_does_not_authorize_non_practitioner_clinical_use(category):
    assert decide(actor_category=category).decision == "deny"


def test_practitioner_must_be_authenticated_and_linked_to_profile():
    assert decide(actor_user_id=None).decision == "deny"
    assert decide(linked_practitioner_user_id="other-user").decision == "deny"
    assert decide(actor_practitioner_id=None).decision == "deny"


def test_latest_applicable_decision_wins_and_regrant_must_be_newer():
    older_active = consent(
        consent_id="old-active",
        granted_at=NOW - timedelta(days=2),
        expires_at=NOW + timedelta(days=2),
    )
    revoked = consent(
        consent_id="revoked",
        status="revoked",
        granted_at=NOW - timedelta(days=1),
        revoked_at=NOW - timedelta(minutes=1),
    )
    assert decide(evidence=[older_active, revoked]).decision == "deny"
    assert decide(evidence=[revoked, older_active]).decision == "deny"

    later_regrant = consent(
        consent_id="regrant",
        granted_at=NOW,
        effective_from=NOW,
        expires_at=NOW + timedelta(days=1),
    )
    assert decide(evidence=[revoked, later_regrant]).allowed

    unverified_revocation = consent(
        consent_id="unverified-revocation",
        status="revoked",
        granted_at=NOW - timedelta(days=1),
        revoked_at=NOW,
        decision_authority_verified=False,
    )
    assert decide(evidence=[older_active, unverified_revocation]).decision == "deny"


def test_latest_narrower_or_expired_record_does_not_fall_back_to_older_broad_record():
    older_full = consent(
        consent_id="old-full",
        access_level="full",
        granted_at=NOW - timedelta(days=2),
        expires_at=NOW + timedelta(days=2),
    )
    newer_read = consent(
        consent_id="new-read",
        access_level="read",
        granted_at=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(days=1),
    )
    assert decide(action="update", evidence=[older_full, newer_read]).decision == "deny"

    newer_expired = consent(
        consent_id="new-expired",
        granted_at=NOW - timedelta(hours=2),
        expires_at=NOW,
    )
    assert decide(evidence=[older_full, newer_expired]).decision == "deny"


def test_ambiguous_same_time_records_deny_and_unaccepted_draft_does_not_supersede():
    first = consent(consent_id="first")
    second = consent(consent_id="second")
    assert decide(evidence=[first, second]).decision == "deny"

    draft = consent(
        consent_id="draft",
        status="draft",
        granted_at=NOW,
    )
    assert decide(evidence=[first, draft]).allowed


def test_all_clinical_resources_allow_only_when_the_consent_scope_contains_resource():
    for resource in CLINICAL_RESOURCES:
        scoped = consent(resource_families=frozenset({resource}))
        assert decide(resource_family=resource, evidence=[scoped]).allowed


def test_multiple_records_cannot_be_combined_to_fill_different_scope_dimensions():
    resource_match_only = consent(
        consent_id="resource-only",
        practitioner_id="another-practitioner",
    )
    recipient_match_only = consent(
        consent_id="recipient-only",
        resource_families=frozenset({"clinical_document"}),
    )
    assert decide(evidence=[resource_match_only, recipient_match_only]).decision == "deny"


def test_bad_context_unknown_resource_and_unhandled_action_deny():
    assert decide(organization_id=None).decision == "deny"
    assert decide(patient_id=None).decision == "deny"
    assert decide(now=NOW.replace(tzinfo=None)).decision == "deny"
    assert decide(resource_family="unknown").decision == "deny"
    assert decide(action="delete").decision == "deny"
    assert decide(requirement=None).decision == "deny"
    assert decide(evidence=None).decision == "deny"
