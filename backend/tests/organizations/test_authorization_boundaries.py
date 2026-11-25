from uuid import UUID

import pytest
from fastapi import HTTPException

from app.modules.organizations import dependencies
from app.modules.organizations.exceptions import OrganizationAccessDeniedError
from app.core.role_catalogue import ORGANIZATION_ADMINISTRATOR, PRACTITIONER

ORG_A = UUID("11111111-1111-4111-8111-111111111111")
ORG_B = UUID("22222222-2222-4222-8222-222222222222")


def member_context(organization_id=ORG_A):
    return {
        "id": "user-1",
        "organization_ids": [str(organization_id)],
        "roles": [
            {
                "name": "practitioner",
                "role_type": "organization",
                "organization_id": str(organization_id),
                "category": PRACTITIONER,
            }
        ],
    }


def admin_context(*organization_ids):
    return {
        "id": "user-1",
        "organization_ids": [str(value) for value in organization_ids],
        "roles": [
            {
                "name": "org_admin",
                "role_type": "organization",
                "organization_id": str(value),
                "category": ORGANIZATION_ADMINISTRATOR,
            }
            for value in organization_ids
        ],
    }


def organization(organization_id=ORG_A):
    return {"id": str(organization_id), "name": "Test organization"}


def test_membership_is_checked_before_privileged_organization_lookup(mocker):
    lookup = mocker.patch.object(dependencies, "get_organization")

    with pytest.raises(OrganizationAccessDeniedError):
        dependencies.require_organization_member(
            organization_id=ORG_A,
            current_user=member_context(ORG_B),
        )

    lookup.assert_not_called()


def test_practitioner_membership_does_not_grant_configuration_access(mocker):
    lookup = mocker.patch.object(dependencies, "get_organization")

    with pytest.raises(OrganizationAccessDeniedError):
        dependencies.require_organization_admin(
            organization_id=ORG_A,
            current_user=member_context(ORG_A),
        )

    lookup.assert_not_called()


def test_admin_authority_must_match_exact_organization_before_lookup(mocker):
    lookup = mocker.patch.object(dependencies, "get_organization")

    with pytest.raises(OrganizationAccessDeniedError):
        dependencies.require_organization_admin(
            organization_id=ORG_A,
            current_user=admin_context(ORG_B),
        )

    lookup.assert_not_called()


def test_exact_scope_org_admin_is_authorized_before_lookup(mocker):
    expected = organization()
    lookup = mocker.patch.object(dependencies, "get_organization", return_value=expected)

    result = dependencies.require_organization_admin(
        organization_id=ORG_A,
        current_user=admin_context(ORG_A),
    )

    assert result is expected
    lookup.assert_called_once_with(organization_id=str(ORG_A))


def test_self_scoped_admin_route_resolves_single_organization(mocker):
    expected = organization()
    lookup = mocker.patch.object(dependencies, "get_organization", return_value=expected)

    result = dependencies.require_current_user_organization_admin(
        current_user=admin_context(ORG_A),
    )

    assert result is expected
    lookup.assert_called_once_with(organization_id=str(ORG_A))


def test_self_scoped_admin_route_denies_multiple_organizations_before_lookup(mocker):
    lookup = mocker.patch.object(dependencies, "get_organization")

    with pytest.raises(HTTPException) as exc:
        dependencies.require_current_user_organization_admin(
            current_user=admin_context(ORG_A, ORG_B),
        )

    assert exc.value.status_code == 403
    lookup.assert_not_called()


def test_self_scoped_admin_route_denies_practitioner_before_lookup(mocker):
    lookup = mocker.patch.object(dependencies, "get_organization")

    with pytest.raises(HTTPException) as exc:
        dependencies.require_current_user_organization_admin(
            current_user=member_context(ORG_A),
        )

    assert exc.value.status_code == 403
    lookup.assert_not_called()
