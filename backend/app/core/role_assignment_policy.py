"""Policy for granting and revoking user role assignments (SPEC-02)."""

from fastapi import HTTPException, status

from app.core.role_catalogue import (
    ORGANIZATION_ADMINISTRATOR,
    PATIENT,
    PRACTITIONER,
    SYSTEM_ADMINISTRATOR,
    UNMAPPED,
    classify_role_assignment,
    has_scoped_category,
)


def authorize_role_change(
    *,
    actor_id: str,
    actor_roles: list[dict],
    target_user_id: str,
    role_name: str,
    role_type: str,
    organization_id: str | None,
    role_organization_id: str | None,
    role_is_active: bool,
    action: str,
    actor_type: str = "user",
) -> str:
    """Validate delegation and scope. Return the target role category.

    Organization administrators may manage practitioner-category assignments
    only in their own organization. System administrators may manage
    organization-admin and system-admin assignments through the separate
    system-administration path. Patient roles are created only by trusted
    onboarding code. No actor may grant a role to themselves.
    """
    if action not in {"assign", "revoke"}:
        raise ValueError("Unsupported role-change action")

    category = classify_role_assignment(
        role_name=role_name,
        role_type=role_type,
        organization_id=organization_id,
        role_organization_id=role_organization_id,
        role_is_active=role_is_active,
    )
    if category == UNMAPPED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role is inactive, unknown, or has invalid scope",
        )

    if action == "assign" and actor_type == "user" and str(actor_id) == str(target_user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Users cannot assign roles to themselves",
        )

    if category == PATIENT:
        if actor_type == "system" and action == "assign":
            return category
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Patient roles are assigned only by trusted onboarding",
        )

    if category == PRACTITIONER:
        if organization_id is None or not has_scoped_category(
            actor_roles, ORGANIZATION_ADMINISTRATOR, organization_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="An administrator for this organization is required",
            )
        return category

    if category in {ORGANIZATION_ADMINISTRATOR, SYSTEM_ADMINISTRATOR}:
        if actor_type == "system" and action == "assign":
            return category
        if not has_scoped_category(actor_roles, SYSTEM_ADMINISTRATOR):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="System administrator authority is required for this role",
            )
        return category

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Role assignment is not permitted",
    )
