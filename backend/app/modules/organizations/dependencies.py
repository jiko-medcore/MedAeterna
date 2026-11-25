from uuid import UUID

from fastapi import Depends

from app.core.role_assignment_policy import resolve_single_org_admin_organization_id
from app.core.security import get_current_user
from app.core.role_catalogue import ORGANIZATION_ADMINISTRATOR, has_scoped_category
from .queries import get_organization
from .exceptions import OrganizationAccessDeniedError


def _user_has_organization_access(
    current_user: dict,
    organization_id: UUID | str,
) -> bool:
    """Check interim membership from the verified active role context.

    get_current_user() derives organization_ids only from active, recognized,
    correctly scoped practitioner and organization-administrator assignments.
    This helper does not grant organization-administrator authority.
    """
    organization_ids = current_user.get("organization_ids") or []
    return str(organization_id) in {str(org_id) for org_id in organization_ids}


def _require_organization_membership(
    current_user: dict,
    organization_id: UUID | str,
) -> None:
    if not _user_has_organization_access(current_user, organization_id):
        raise OrganizationAccessDeniedError()


def _require_organization_admin_authority(
    current_user: dict,
    organization_id: UUID | str,
) -> None:
    """Require both interim membership and exact-scope administrator authority."""
    _require_organization_membership(current_user, organization_id)
    if not has_scoped_category(
        current_user.get("roles", []),
        ORGANIZATION_ADMINISTRATOR,
        str(organization_id),
    ):
        raise OrganizationAccessDeniedError()


def require_organization_member(
    organization_id: UUID,
    current_user=Depends(get_current_user),
):
    """Verify membership before any privileged organization lookup.

    Membership is currently evidenced by an active, recognized, correctly
    scoped practitioner or organization-administrator assignment. It does not
    imply authority to read or change organization configuration.
    """
    _require_organization_membership(current_user, organization_id)
    return get_organization(organization_id=str(organization_id))


def require_organization_admin(
    organization_id: UUID,
    current_user=Depends(get_current_user),
):
    """Require exact-organization administrator authority before lookup."""
    _require_organization_admin_authority(current_user, organization_id)
    return get_organization(organization_id=str(organization_id))


def require_organization_access(
    organization=Depends(require_organization_admin),
):
    """Authorize organization-configuration reads under SPEC-03.

    SPEC-03 does not grant practitioners general organization-configuration
    reads. Until a separate organization-read rule is approved, this dependency
    requires an administrator assignment for the exact organization.
    """
    return organization


def require_organization_admin_for_org_id(
    org_id: UUID,
    current_user=Depends(get_current_user),
):
    """Organization-admin dependency for routes using an org_id path parameter."""
    _require_organization_admin_authority(current_user, org_id)
    return get_organization(organization_id=str(org_id))


def require_current_user_organization_admin(
    current_user=Depends(get_current_user),
):
    """Resolve a self-scoped organization only for a single org administrator.

    This is for routes without an organization path/query parameter. Multiple
    organization-admin assignments are ambiguous and fail closed.
    """
    organization_id = resolve_single_org_admin_organization_id(
        current_user.get("roles", [])
    )
    _require_organization_admin_authority(current_user, organization_id)
    return get_organization(organization_id=str(organization_id))


# Future dependencies require explicit policy before implementation.
def require_organization_owner():
    pass


def require_department_manager():
    pass


def require_practitioner():
    pass


def require_billing_admin():
    pass
