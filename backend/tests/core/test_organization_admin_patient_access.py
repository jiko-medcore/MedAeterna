import pytest

from app.core.action_authorization import evaluate_action
from app.core.organization_admin_patient_access import (
    ADMIN_PATIENT_PURPOSE_FIELDS,
    evaluate_organization_admin_patient_access,
)
from app.core.role_catalogue import (
    ORGANIZATION_ADMINISTRATOR,
    PATIENT,
    PRACTITIONER,
)


ORG_ADMIN = [{"category": ORGANIZATION_ADMINISTRATOR, "organization_id": "org-a"}]


@pytest.mark.parametrize(
    "purpose",
    ["registration_identity", "appointment_coordination", "billing_administration"],
)
def test_org_admin_can_read_only_allowlisted_fields_for_approved_purpose(purpose):
    allowed = evaluate_organization_admin_patient_access(
        actor_roles=ORG_ADMIN,
        organization_id="org-a",
        subject_patient_id="patient-1",
        purpose=purpose,
        requested_fields=ADMIN_PATIENT_PURPOSE_FIELDS[purpose],
        patient_admin_link_verified=True,
        audit_recorded=True,
    )

    assert allowed.allowed


def test_admin_data_access_requires_verified_patient_link_and_audit():
    result = evaluate_organization_admin_patient_access(
        actor_roles=ORG_ADMIN,
        organization_id="org-a",
        subject_patient_id="patient-1",
        purpose="registration_identity",
        requested_fields={"patient_reference", "patient_name"},
    )

    assert result.decision == "conditional"
    assert result.missing_conditions == (
        "audit_recorded",
        "patient_admin_link_verified",
    )


def test_admin_patient_link_must_be_in_the_exact_organization():
    result = evaluate_organization_admin_patient_access(
        actor_roles=ORG_ADMIN,
        organization_id="org-b",
        subject_patient_id="patient-1",
        purpose="registration_identity",
        requested_fields={"patient_reference", "patient_name"},
        patient_admin_link_verified=True,
        audit_recorded=True,
    )

    assert result.decision == "deny"


@pytest.mark.parametrize("purpose", ["", "clinical_care", "general_administration"])
def test_unapproved_or_generic_purpose_denies(purpose):
    result = evaluate_organization_admin_patient_access(
        actor_roles=ORG_ADMIN,
        organization_id="org-a",
        subject_patient_id="patient-1",
        purpose=purpose,
        requested_fields={"patient_reference"},
        patient_admin_link_verified=True,
        audit_recorded=True,
    )

    assert result.decision == "deny"


@pytest.mark.parametrize(
    "field",
    [
        "blood_group",
        "gender",
        "diagnosis",
        "medication",
        "lab_result",
        "encounter_note",
        "consent_record",
        "emergency_contact",
        "profile_image_url",
    ],
)
def test_clinical_sensitive_or_nonminimum_fields_are_never_returned(field):
    result = evaluate_organization_admin_patient_access(
        actor_roles=ORG_ADMIN,
        organization_id="org-a",
        subject_patient_id="patient-1",
        purpose="billing_administration",
        requested_fields={"patient_reference", field},
        patient_admin_link_verified=True,
        audit_recorded=True,
    )

    assert result.decision == "deny"


def test_wrong_role_full_profile_and_nonread_actions_deny():
    for role in (PATIENT, PRACTITIONER):
        result = evaluate_organization_admin_patient_access(
            actor_roles=[{"category": role, "organization_id": "org-a"}],
            organization_id="org-a",
            subject_patient_id="patient-1",
            purpose="registration_identity",
            requested_fields={"patient_reference"},
            patient_admin_link_verified=True,
            audit_recorded=True,
        )
        assert result.decision == "deny"

    full_profile = evaluate_action(
        actor_roles=ORG_ADMIN,
        resource="patient_profile",
        action="read",
        organization_id="org-a",
        verified_conditions={"patient_admin_link_verified", "audit_recorded"},
    )
    assert full_profile.decision == "deny"

    for action in ("create", "update", "delete", "administer", "retry"):
        result = evaluate_action(
            actor_roles=ORG_ADMIN,
            resource="patient_admin_data",
            action=action,
            organization_id="org-a",
        )
        assert result.decision == "deny"


def test_bulk_access_and_missing_patient_subject_deny():
    base = {
        "actor_roles": ORG_ADMIN,
        "organization_id": "org-a",
        "subject_patient_id": "patient-1",
        "purpose": "registration_identity",
        "requested_fields": {"patient_reference"},
        "patient_admin_link_verified": True,
        "audit_recorded": True,
    }

    assert evaluate_organization_admin_patient_access(**base, bulk_access=True).decision == "deny"
    assert evaluate_organization_admin_patient_access(
        **{**base, "subject_patient_id": None}
    ).decision == "deny"


def test_each_purpose_has_a_distinct_bounded_field_set():
    assert ADMIN_PATIENT_PURPOSE_FIELDS["registration_identity"] == {
        "patient_reference",
        "patient_name",
    }
    assert "contact_phone" not in ADMIN_PATIENT_PURPOSE_FIELDS["registration_identity"]
    assert "billing_status" not in ADMIN_PATIENT_PURPOSE_FIELDS["appointment_coordination"]
    assert "billing_reference" in ADMIN_PATIENT_PURPOSE_FIELDS["billing_administration"]
