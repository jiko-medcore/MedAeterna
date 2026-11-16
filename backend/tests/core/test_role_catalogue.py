from uuid import uuid4

import pytest

from app.core.role_catalogue import (
    ORGANIZATION_ADMINISTRATOR,
    PATIENT,
    PRACTITIONER,
    SYSTEM_ADMINISTRATOR,
    UNMAPPED,
    classify_role_assignment,
    has_scoped_category,
    normalize_role_assignment,
)
from app.modules.organizations.dependencies import require_organization_admin
from app.modules.organizations.exceptions import OrganizationAccessDeniedError


def assignment(name, role_type, organization_id=None, role_organization_id=None, active=True):
    return normalize_role_assignment(
        role_name=name,
        role_type=role_type,
        organization_id=organization_id,
        role_organization_id=role_organization_id,
        role_is_active=active,
    )


@pytest.mark.parametrize(
    ("name", "scope", "organization_id", "role_organization_id", "expected"),
    [
        ("patient", "system", None, None, PATIENT),
        ("super_admin", "system", None, None, SYSTEM_ADMINISTRATOR),
        ("practitioner", "organization", "org-a", "org-a", PRACTITIONER),
        ("doctor", "organization", "org-a", "org-a", PRACTITIONER),
        ("clinician", "organization", "org-a", "org-a", PRACTITIONER),
        ("org_admin", "organization", "org-a", "org-a", ORGANIZATION_ADMINISTRATOR),
    ],
)
def test_known_role_is_classified_only_at_its_declared_scope(
    name, scope, organization_id, role_organization_id, expected
):
    assert classify_role_assignment(
        name,
        scope,
        organization_id,
        role_organization_id,
        role_is_active=True,
    ) == expected


@pytest.mark.parametrize(
    ("name", "scope", "organization_id", "role_organization_id", "active"),
    [
        ("admin", "system", None, None, True),
        ("admin", "organization", "org-a", "org-a", True),
        ("patient", "organization", "org-a", "org-a", True),
        ("super_admin", "organization", "org-a", "org-a", True),
        ("org_admin", "system", None, None, True),
        ("org_admin", "organization", "org-a", "org-b", True),
        ("org_admin", "organization", "org-a", "org-a", False),
        ("unknown_role", "organization", "org-a", "org-a", True),
    ],
)
def test_ambiguous_inactive_or_mismatched_assignment_is_unmapped(
    name, scope, organization_id, role_organization_id, active
):
    assert classify_role_assignment(
        name,
        scope,
        organization_id,
        role_organization_id,
        role_is_active=active,
    ) == UNMAPPED


def test_org_admin_assignment_applies_only_to_matching_organization():
    org_a = str(uuid4())
    org_b = str(uuid4())
    roles = [assignment("org_admin", "organization", org_a, org_a)]

    assert has_scoped_category(roles, ORGANIZATION_ADMINISTRATOR, org_a)
    assert not has_scoped_category(roles, ORGANIZATION_ADMINISTRATOR, org_b)
    assert not has_scoped_category(roles, ORGANIZATION_ADMINISTRATOR)


def test_system_admin_does_not_imply_org_admin():
    roles = [assignment("super_admin", "system")]

    assert has_scoped_category(roles, SYSTEM_ADMINISTRATOR)
    assert not has_scoped_category(
        roles, ORGANIZATION_ADMINISTRATOR, str(uuid4())
    )


def test_organization_admin_dependency_allows_own_organization():
    org_id = str(uuid4())
    organization = {"id": org_id}
    user = {"roles": [assignment("org_admin", "organization", org_id, org_id)]}

    assert require_organization_admin(
        organization=organization,
        current_user=user,
    ) is organization


def test_organization_admin_dependency_denies_another_organization():
    assigned_org_id = str(uuid4())
    target_org_id = str(uuid4())
    user = {
        "roles": [
            assignment("org_admin", "organization", assigned_org_id, assigned_org_id)
        ]
    }

    with pytest.raises(OrganizationAccessDeniedError):
        require_organization_admin(
            organization={"id": target_org_id},
            current_user=user,
        )


def test_system_admin_cannot_pass_organization_admin_dependency():
    user = {"roles": [assignment("super_admin", "system")]}

    with pytest.raises(OrganizationAccessDeniedError):
        require_organization_admin(
            organization={"id": str(uuid4())},
            current_user=user,
        )
