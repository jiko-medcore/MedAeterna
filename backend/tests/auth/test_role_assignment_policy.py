from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.role_assignment_policy import authorize_role_change
from app.core.role_catalogue import (
    ORGANIZATION_ADMINISTRATOR,
    PRACTITIONER,
    SYSTEM_ADMINISTRATOR,
    normalize_role_assignment,
)


def role(name, scope, org_id=None):
    return normalize_role_assignment(
        role_name=name,
        role_type=scope,
        organization_id=org_id,
        role_organization_id=org_id,
        role_is_active=True,
    )


def test_org_admin_can_grant_practitioner_role_in_own_org():
    org_id = str(uuid4())
    category = authorize_role_change(
        actor_id=str(uuid4()),
        actor_roles=[role("org_admin", "organization", org_id)],
        target_user_id=str(uuid4()),
        role_name="clinician",
        role_type="organization",
        organization_id=org_id,
        role_organization_id=org_id,
        role_is_active=True,
        action="assign",
    )
    assert category == PRACTITIONER


def test_org_admin_cannot_grant_role_in_another_org():
    actor_org = str(uuid4())
    target_org = str(uuid4())
    with pytest.raises(HTTPException) as error:
        authorize_role_change(
            actor_id=str(uuid4()),
            actor_roles=[role("org_admin", "organization", actor_org)],
            target_user_id=str(uuid4()),
            role_name="practitioner",
            role_type="organization",
            organization_id=target_org,
            role_organization_id=target_org,
            role_is_active=True,
            action="assign",
        )
    assert error.value.status_code == 403


@pytest.mark.parametrize("role_name", ["org_admin", "admin", "super_admin", "patient", "staff"])
def test_org_admin_cannot_delegate_admin_system_patient_or_unmapped_roles(role_name):
    org_id = str(uuid4())
    scope = "system" if role_name in {"super_admin", "patient"} else "organization"
    role_org_id = None if scope == "system" else org_id
    assignment_org_id = None if scope == "system" else org_id
    with pytest.raises(HTTPException):
        authorize_role_change(
            actor_id=str(uuid4()),
            actor_roles=[role("org_admin", "organization", org_id)],
            target_user_id=str(uuid4()),
            role_name=role_name,
            role_type=scope,
            organization_id=assignment_org_id,
            role_organization_id=role_org_id,
            role_is_active=True,
            action="assign",
        )


def test_system_admin_can_grant_org_admin_to_another_user():
    org_id = str(uuid4())
    assert authorize_role_change(
        actor_id=str(uuid4()),
        actor_roles=[role("super_admin", "system")],
        target_user_id=str(uuid4()),
        role_name="org_admin",
        role_type="organization",
        organization_id=org_id,
        role_organization_id=org_id,
        role_is_active=True,
        action="assign",
    ) == ORGANIZATION_ADMINISTRATOR


def test_system_admin_can_grant_system_admin_to_another_user():
    assert authorize_role_change(
        actor_id=str(uuid4()),
        actor_roles=[role("super_admin", "system")],
        target_user_id=str(uuid4()),
        role_name="super_admin",
        role_type="system",
        organization_id=None,
        role_organization_id=None,
        role_is_active=True,
        action="assign",
    ) == SYSTEM_ADMINISTRATOR


def test_system_admin_cannot_grant_system_role_to_self():
    actor_id = str(uuid4())
    with pytest.raises(HTTPException) as error:
        authorize_role_change(
            actor_id=actor_id,
            actor_roles=[role("super_admin", "system")],
            target_user_id=actor_id,
            role_name="super_admin",
            role_type="system",
            organization_id=None,
            role_organization_id=None,
            role_is_active=True,
            action="assign",
        )
    assert error.value.status_code == 403


def test_org_admin_cannot_revoke_assignment_outside_own_org():
    actor_org = str(uuid4())
    target_org = str(uuid4())
    with pytest.raises(HTTPException) as error:
        authorize_role_change(
            actor_id=str(uuid4()),
            actor_roles=[role("org_admin", "organization", actor_org)],
            target_user_id=str(uuid4()),
            role_name="doctor",
            role_type="organization",
            organization_id=target_org,
            role_organization_id=target_org,
            role_is_active=True,
            action="revoke",
        )
    assert error.value.status_code == 403


def test_inactive_and_unmapped_roles_cannot_be_delegated():
    org_id = str(uuid4())
    with pytest.raises(HTTPException) as inactive:
        authorize_role_change(
            actor_id=str(uuid4()),
            actor_roles=[role("org_admin", "organization", org_id)],
            target_user_id=str(uuid4()),
            role_name="doctor",
            role_type="organization",
            organization_id=org_id,
            role_organization_id=org_id,
            role_is_active=False,
            action="assign",
        )
    assert inactive.value.status_code == 400

    with pytest.raises(HTTPException) as unmapped:
        authorize_role_change(
            actor_id=str(uuid4()),
            actor_roles=[role("org_admin", "organization", org_id)],
            target_user_id=str(uuid4()),
            role_name="staff",
            role_type="organization",
            organization_id=org_id,
            role_organization_id=org_id,
            role_is_active=True,
            action="assign",
        )
    assert unmapped.value.status_code == 400
