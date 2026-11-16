from fastapi import (
    APIRouter, 
    Depends, 
    HTTPException, 
    UploadFile, 
    File,
    BackgroundTasks
)
from app.modules.organizations.schemas import (
    OrganizationCreate,
    OrganizationUpdate,
    RoleAssignment,
    OnboardingInvite,
    AcceptInviteRequest
)
from app.modules.organizations.service import (
    create_organization,
    update_organization,
    assign_user_role,
    create_invitation,
    accept_invitation
)
from app.core.security import (
    get_current_user,
    require_permission
)
from app.modules.auth.role_assignment_schemas import RoleAssignmentRevocation
from app.modules.auth.role_assignment_service import revoke_organization_role
from app.modules.organizations.dependencies import require_organization_admin_for_org_id
from app.modules.organizations.queries import (
    get_user_organization_id,
    get_organization,
)
from app.core.supabase_client import supabase
from app.shared.tasks.event_tasks import process_events_task
from .profile.router import (
    router as profile_router,
)
from .departments.router import (
    router as departments_router,
)
from .healthcare_services.router import (
    router as healthcare_service_router
)
from .operating_hours.router import ( 
    router as operating_hours_router
)
from .branding.router import (
    router as branding_router
)


# ---------------------------------------
# Router Setup 
# ---------------------------------------
router = APIRouter(prefix="/organizations", tags=["Organizations"])


# ---------------------------------------
# PROFILE ROUTER 
# ---------------------------------------
router.include_router(profile_router)


# ---------------------------------------
# DEPARTMENTS ROUTER 
# ---------------------------------------
router.include_router(departments_router)


# ---------------------------------------
# HEALTHCARE SERVICE ROUTER 
# ---------------------------------------
router.include_router(healthcare_service_router)

# ---------------------------------------
# OPERATING HOURS ROUTER
# ---------------------------------------
router.include_router(operating_hours_router)


# ---------------------------------------
# BRANDING ROUTER
# ---------------------------------------
router.include_router(branding_router)




#----------------------------------------- 
# Organization Registration Endpoint
# ----------------------------------------
@router.post("/register")
def register_organization(
    payload: OrganizationCreate,
    background_tasks: BackgroundTasks
):
    result = create_organization(payload)

    background_tasks.add_task(process_events_task)

    return result


# -----------------------------------------
# Get My Organization Endpoint 
# -----------------------------------------
@router.get("/me")
def get_my_organization(
    current_user=Depends(get_current_user)
):
    org_id = get_user_organization_id(current_user["id"])

    return get_organization(org_id)


# --------------------------------------------
# Upload Organization Logo Endpoint
# --------------------------------------------
@router.post("/upload-logo")
async def upload_logo(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user)
) -> dict:

    # Get org id
    org_id = get_user_organization_id(current_user["id"])

    file_ext = file.filename.split(".")[-1]
    file_path = f"{org_id}.{file_ext}"

    file_bytes = await file.read()

    supabase.storage.from_("organization-logos").upload(
        path=file_path,
        file=file_bytes,
        file_options={"content-type": file.content_type}
    )

    public_url = supabase.storage.from_("organization-logos").get_public_url(file_path)

    supabase.table("organizations").update({
        "logo_url": public_url
    }).eq("id", org_id).execute()

    return {
        "message": "Logo uploaded successfully",
        "logo_url": public_url
    }


# ---------------------------------------------
# Update Organization Endpoint
# ---------------------------------------------
@router.put("/update")
def update_my_organization(
    payload: OrganizationUpdate,
    current_user=Depends(get_current_user),
    _=Depends(require_permission("manage_organization"))
):

    # get user org_id
    org_id = get_user_organization_id(current_user["id"])

    return update_organization(org_id, payload)


# -----------------------------------------------
# Role Management Endpoints
# -----------------------------------------------
@router.post("/{org_id}/assign-role")
def assign_role_to_user(
    org_id: str,
    role_data: RoleAssignment,
    current_user=Depends(get_current_user),
    organization=Depends(require_organization_admin_for_org_id),
):
    if str(role_data.org_id) != org_id:
        raise HTTPException(400, "Organization mismatch")

    payload = role_data.model_copy(update={"org_id": org_id})
    return assign_user_role(
        payload,
        actor_id=current_user["id"],
        actor_roles=current_user.get("roles", []),
    )


@router.delete("/{org_id}/assign-role")
def revoke_role_from_user(
    org_id: str,
    role_data: RoleAssignmentRevocation,
    current_user=Depends(get_current_user),
    organization=Depends(require_organization_admin_for_org_id),
):
    if role_data.organization_id and str(role_data.organization_id) != org_id:
        raise HTTPException(400, "Organization mismatch")
    return revoke_organization_role(
        actor_id=current_user["id"],
        actor_roles=current_user.get("roles", []),
        target_user_id=str(role_data.user_id),
        role_name=role_data.role_name,
        organization_id=org_id,
        reason=role_data.reason,
    )


# ------------------------------------------------
# Onboarding Invite Endpoint
# ------------------------------------------------
@router.post("/{org_id}/invite")
def invite_user(
    org_id: str,
    invite_data: OnboardingInvite,
    current_user=Depends(get_current_user),
    organization=Depends(require_organization_admin_for_org_id),
):
    if invite_data.org_id != org_id:
        raise HTTPException(400, "Organization mismatch")
    return create_invitation(
        org_id,
        invite_data.email,
        invite_data.role_name,
        current_user["id"],
        actor_roles=current_user.get("roles", []),
        actor_email=current_user.get("email", ""),
    )


# --------------------------------------------------
# Accept Invitation Endpoint
# --------------------------------------------------
@router.post("/accept-invite")
def accept_invite(payload: AcceptInviteRequest):
    return accept_invitation(payload)
