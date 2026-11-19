import pytest

from app.core.action_authorization import evaluate_action
from app.core.role_catalogue import (
    ORGANIZATION_ADMINISTRATOR,
    PRACTITIONER,
    SYSTEM_ADMINISTRATOR,
)
from app.core.system_admin_patient_access import (
    PATIENT_DATA_RESOURCES,
    evaluate_system_admin_patient_data_access,
)


SYSTEM_ADMIN = [{"category": SYSTEM_ADMINISTRATOR, "organization_id": None}]


@pytest.mark.parametrize("resource", sorted(PATIENT_DATA_RESOURCES))
@pytest.mark.parametrize("action", ["read", "create", "update", "delete", "administer", "retry"])
def test_system_admin_patient_data_access_is_explicitly_denied(resource, action):
    result = evaluate_system_admin_patient_data_access(
        actor_roles=SYSTEM_ADMIN,
        resource=resource,
        action=action,
    )

    assert result.decision == "deny"


def test_break_glass_request_remains_denied_even_with_system_admin_assignment():
    result = evaluate_system_admin_patient_data_access(
        actor_roles=SYSTEM_ADMIN,
        resource="clinical_record",
        action="read",
        break_glass_requested=True,
    )

    assert result.decision == "deny"
    assert "does not authorize" in result.reason


def test_org_admin_and_unmapped_actor_cannot_use_system_admin_guard():
    for roles in (
        [{"category": ORGANIZATION_ADMINISTRATOR, "organization_id": "org-a"}],
        [{"category": "unmapped", "organization_id": None}],
    ):
        result = evaluate_system_admin_patient_data_access(
            actor_roles=roles,
            resource="patient_profile",
            action="read",
        )
        assert result.decision == "deny"
        assert "assignment is required" in result.reason


def test_unknown_non_patient_resource_is_not_authorized_by_patient_guard():
    result = evaluate_system_admin_patient_data_access(
        actor_roles=SYSTEM_ADMIN,
        resource="platform_configuration",
        action="read",
    )

    assert result.decision == "deny"
    assert "outside the patient-data boundary" in result.reason


def test_separately_scoped_practitioner_path_remains_subject_to_clinical_gates():
    roles = SYSTEM_ADMIN + [
        {"category": PRACTITIONER, "organization_id": "org-a"}
    ]
    system_path = evaluate_system_admin_patient_data_access(
        actor_roles=roles,
        resource="clinical_record",
        action="read",
    )
    assert system_path.decision == "deny"

    practitioner_path = evaluate_action(
        actor_roles=roles,
        resource="clinical_record",
        action="read",
        organization_id="org-a",
        verified_conditions={
            "patient_relationship",
            "consent_if_required",
            "clinical_workflow",
        },
    )
    assert practitioner_path.allowed
