from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.modules.practitioner_roles.schemas import (
    PractitionerRoleAssign,
    PractitionerRoleUpdate,
)
from app.modules.practitioner_roles.service import (
    assign_practitioner_role,
    get_my_practitioner_roles,
    get_organization_practitioners,
    update_practitioner_role
)


router = APIRouter(
    prefix="/practitioner-roles",
    tags=["Practitioner Roles"]
)


# ----- Practitioner Role Assignment Router -----
@router.post("/")
def assign_role(
    payload: PractitionerRoleAssign,
    current_user=Depends(get_current_user)
):

    return assign_practitioner_role(
        actor_id=current_user["id"],
        actor_roles=current_user.get("roles", []),
        target_practitioner_id=payload.practitioner_id,
        payload=payload,
    )


# ----- Get Practitioner Role endpoint -----
@router.get("/me")
def my_roles(
    user=Depends(get_current_user)
):

    return get_my_practitioner_roles(
        user["id"]
    )


# ---- List Practitioners Organizations endpoint -----
@router.get("/organization/{organization_id}")
def organization_practitioners(
    organization_id: str,
    current_user=Depends(get_current_user)
):

    return get_organization_practitioners(
        actor_roles=current_user.get("roles", []),
        organization_id=organization_id,
    )


# ---- Update Practitioners Role endpoint -----
@router.patch("/{role_id}")
def update_role(
    role_id: str,
    payload: PractitionerRoleUpdate,
    current_user=Depends(get_current_user)
):

    return update_practitioner_role(
        actor_id=current_user["id"],
        actor_roles=current_user.get("roles", []),
        role_id=role_id,
        payload=payload,
    )
