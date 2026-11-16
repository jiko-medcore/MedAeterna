from uuid import UUID
from fastapi import Depends
from app.core.security import get_current_user
from app.core.role_catalogue import ORGANIZATION_ADMINISTRATOR, has_scoped_category
from .queries import get_organization
from .exceptions import (
    OrganizationAccessDeniedError,
    OrganizationNotFoundError,
)


# ------------------------------------
# Members Check Helper
# ------------------------------------
def _user_has_organization_access(
    current_user: dict,
    organization_id: UUID,
) -> bool:
    """
    Temporary organization access check until the
    organization membership module is implemented.
    """

    organization_ids = current_user.get(
        "organization_ids",
        []
    )

    return str(organization_id) in {
        str(org_id)
        for org_id in organization_ids
    }

# ---------------------------------
#   BASE DEPENDENCY
# ---------------------------------
def require_organization_member(
    organization_id: UUID,
    current_user=Depends(get_current_user),
):
    """
    Ensure the authenticated user belongs
    to the requested organization.
    """

    organization = get_organization(
        organization_id=organization_id,
    )

    if organization is None:
        raise OrganizationNotFoundError()

    #
    # TODO:
    # Replace with organization membership
    # query once implemented.
    #

    if not _user_has_organization_access(
        current_user,
        organization_id,
    ):
        raise OrganizationAccessDeniedError()

    return organization


# ---------------------------------
# ORGANIZATION ACCESS DEPENDENCY
# ---------------------------------

def require_organization_access(
    organization=Depends(require_organization_member),
):
    """
    Ensure the authenticated user has access to the
    requested organization.

    This dependency is intended for authenticated
    read operations on organization-scoped resources.

    It currently delegates to require_organization_member()
    so that organization existence and membership checks
    remain centralized.
    """

    return organization


# ---------------------------------
#   ADMIN DEPENDENCY
# ---------------------------------
def require_organization_admin(
    organization=Depends(require_organization_member),
    current_user=Depends(get_current_user),
):
    """
    Ensure the current user is an
    organization administrator.
    """

    #
    # TODO:
    # Replace with role/permission system.
    #

    if not has_scoped_category(
        current_user.get("roles", []),
        ORGANIZATION_ADMINISTRATOR,
        str(organization["id"]),
    ):
        raise OrganizationAccessDeniedError()

    return organization


# ---------------------------------
#   FUTURE DEPENDENCIES
# ---------------------------------
def require_organization_owner():
    pass

def require_department_manager():
    pass

def require_practitioner():
    pass

def require_billing_admin():
    pass
