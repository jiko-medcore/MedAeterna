import pytest
from fastapi import HTTPException

from app.core import security
from app.core.clinical_authorization import (
    APPOINTMENT,
    authorize_practitioner_schedule_access,
    ensure_authorized_context,
    practitioner_organization_ids,
    resolve_practitioner_organization_id,
)
from app.core.role_catalogue import PRACTITIONER


def practitioner_user(*organizations):
    return {
        "id": "user-1",
        # Deliberately include this convenience field to prove it is not used
        # as the source of practitioner organization authority.
        "organization_ids": list(organizations),
        "roles": [
            {"category": PRACTITIONER, "organization_id": org}
            for org in organizations
        ],
    }


def test_practitioner_organization_ids_are_deduplicated_and_deterministic():
    user = practitioner_user("org-b", "org-a", "org-b")

    assert practitioner_organization_ids(user) == ("org-a", "org-b")


def test_practitioner_can_select_one_of_multiple_role_scopes():
    user = practitioner_user("org-a", "org-b")

    assert resolve_practitioner_organization_id(user, "org-b") == "org-b"


def test_multiple_practitioner_scopes_without_selection_are_ambiguous():
    with pytest.raises(HTTPException) as exc:
        resolve_practitioner_organization_id(practitioner_user("org-a", "org-b"))

    assert exc.value.status_code == 403


def test_organization_ids_convenience_field_cannot_create_practitioner_scope():
    user = {
        "id": "user-1",
        "organization_ids": ["org-a"],
        "roles": [],
    }

    with pytest.raises(HTTPException) as exc:
        resolve_practitioner_organization_id(user, "org-a")

    assert exc.value.status_code == 403


def test_requested_organization_must_be_in_practitioner_role_scope():
    user = practitioner_user("org-a")
    user["organization_ids"] = ["org-a", "org-forged"]

    with pytest.raises(HTTPException) as exc:
        resolve_practitioner_organization_id(user, "org-forged")

    assert exc.value.status_code == 403


def test_single_practitioner_scope_can_be_resolved_without_selection():
    assert resolve_practitioner_organization_id(practitioner_user("org-a")) == "org-a"


def test_practitioner_schedule_uses_shared_actor_resolution(monkeypatch):
    monkeypatch.setattr(security, "resolve_practitioner_id", lambda _user_id: "prac-1")

    context = authorize_practitioner_schedule_access(
        practitioner_user("org-a"),
        practitioner_id="prac-1",
        organization_id="org-a",
    )

    assert context["authorized_user_id"] == "user-1"
    assert context["authorized_practitioner_id"] == "prac-1"
    assert context["authorized_organization_id"] == "org-a"
    assert context["authorized_resource"] == APPOINTMENT
    assert context["authorized_action"] == "read"


def test_practitioner_schedule_rejects_path_practitioner_mismatch(monkeypatch):
    monkeypatch.setattr(security, "resolve_practitioner_id", lambda _user_id: "prac-1")

    with pytest.raises(HTTPException) as exc:
        authorize_practitioner_schedule_access(
            practitioner_user("org-a"),
            practitioner_id="prac-other",
            organization_id="org-a",
        )

    assert exc.value.status_code == 403


def test_service_context_does_not_fall_back_to_plain_authenticated_user_id():
    with pytest.raises(HTTPException) as exc:
        ensure_authorized_context(
            {
                "id": "user-1",
                "authorized_resource": APPOINTMENT,
                "authorized_action": "read",
            },
            resource=APPOINTMENT,
            action="read",
        )

    assert exc.value.status_code == 401


def test_service_context_requires_explicit_actor_and_exact_scope():
    ensure_authorized_context(
        {
            "id": "untrusted-fallback",
            "authorized_user_id": "user-1",
            "authorized_resource": APPOINTMENT,
            "authorized_action": "read",
            "authorized_patient_id": "patient-1",
            "authorized_organization_id": "org-1",
            "authorized_resource_id": "appointment-1",
        },
        resource=APPOINTMENT,
        action="read",
        patient_id="patient-1",
        organization_id="org-1",
        resource_id="appointment-1",
    )


@pytest.mark.parametrize(
    "field,expected,kwargs",
    [
        ("authorized_patient_id", "patient-2", {"patient_id": "patient-1"}),
        ("authorized_organization_id", "org-2", {"organization_id": "org-1"}),
        ("authorized_resource_id", "appointment-2", {"resource_id": "appointment-1"}),
    ],
)
def test_service_context_rejects_scope_mismatch(field, expected, kwargs):
    context = {
        "authorized_user_id": "user-1",
        "authorized_resource": APPOINTMENT,
        "authorized_action": "read",
        "authorized_patient_id": "patient-1",
        "authorized_organization_id": "org-1",
        "authorized_resource_id": "appointment-1",
    }
    context[field] = expected

    with pytest.raises(HTTPException) as exc:
        ensure_authorized_context(
            context,
            resource=APPOINTMENT,
            action="read",
            **kwargs,
        )

    assert exc.value.status_code == 403
