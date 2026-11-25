from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.modules.organizations.dependencies import (
    require_current_user_organization_admin,
)
from app.modules.organizations.profile.schemas import (
    OrganizationProfileResponse,
    OrganizationProfileUpdate,
)
from app.modules.organizations.profile.service import (
    get_profile,
    update_profile,
)


router = APIRouter(
    prefix="/profile",
    tags=["Organization Profile"],
)


@router.get(
    "",
    response_model=OrganizationProfileResponse,
)
def get_organization_profile(
    organization=Depends(require_current_user_organization_admin),
):
    return get_profile(str(organization["id"]))


@router.patch(
    "",
    response_model=OrganizationProfileResponse,
)
def update_organization_profile(
    payload: OrganizationProfileUpdate,
    current_user=Depends(get_current_user),
    organization=Depends(require_current_user_organization_admin),
):
    return update_profile(
        organization_id=str(organization["id"]),
        payload=payload,
        actor_id=current_user["id"],
        actor_roles=current_user.get("roles", []),
    )
