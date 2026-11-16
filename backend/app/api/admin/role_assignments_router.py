from fastapi import APIRouter, Depends

from app.core.security import get_current_user, require_role
from app.modules.auth.role_assignment_schemas import (
    RoleAssignmentChange,
    RoleAssignmentRevocation,
)
from app.modules.auth.role_assignment_service import (
    assign_system_managed_role,
    revoke_system_managed_role,
)


router = APIRouter(
    prefix="/admin/role-assignments",
    tags=["System Role Administration"],
)


@router.post("")
def assign_system_managed_role_endpoint(
    payload: RoleAssignmentChange,
    current_user=Depends(require_role("super_admin")),
):
    return assign_system_managed_role(
        actor_id=current_user["id"],
        actor_roles=current_user.get("roles", []),
        target_user_id=str(payload.user_id),
        role_name=payload.role_name,
        organization_id=(
            str(payload.organization_id) if payload.organization_id else None
        ),
        reason=payload.reason,
    )


@router.delete("")
def revoke_system_managed_role_endpoint(
    payload: RoleAssignmentRevocation,
    current_user=Depends(require_role("super_admin")),
):
    return revoke_system_managed_role(
        actor_id=current_user["id"],
        actor_roles=current_user.get("roles", []),
        target_user_id=str(payload.user_id),
        role_name=payload.role_name,
        organization_id=(
            str(payload.organization_id) if payload.organization_id else None
        ),
        reason=payload.reason,
    )
