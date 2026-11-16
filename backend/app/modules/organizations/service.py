from app.core.supabase_client import supabase
from app.core.supabase_admin import supabase_admin
from app.core.role_assignment_policy import authorize_role_change
from app.core.role_catalogue import normalize_role_assignment
from app.modules.auth.role_assignment_service import (
    assign_onboarding_role,
    assign_organization_role,
)
from app.modules.organizations.schemas import (
    OrganizationCreate,
    OrganizationUpdate,
    AcceptInviteRequest,
    RoleAssignment,
)
from app.core.events.emitter import emit_event
from app.core.events.schemas import EventTypes
from fastapi import HTTPException
import uuid
from datetime import (
    datetime, 
    timedelta,
    timezone,
)


# ---------------------------------
#  Organization Creation Service
# ---------------------------------
def create_organization(
        payload: OrganizationCreate
        ):

    # Create admin user in Supabase Auth
    auth_response = supabase_admin.auth.admin.create_user({
        "email": payload.admin_email,
        "password": payload.admin_password,
        "email_confirm": True
    })

    if not auth_response.user:
        raise HTTPException(400, "Failed to create admin user")

    admin_id = auth_response.user.id

    # ----- Create Organization -----
    org_response = (
        supabase_admin
        .table("organizations")
        .insert(payload.model_dump(exclude={"admin_email", "admin_password"}))
        .execute()
    )

    if not org_response.data:
        raise Exception("Failed to create organization")

    org = org_response.data[0]
    org_id = org["id"]

    # ----- Create Default Roles for Org -----
    default_roles = ["org_admin", "practitioner", "staff"]

    # Insert Default Roles
    roles_to_insert = [
        {
            "name": role,
            "organization_id": org_id,
            "role_type": "organization"
        }
        for role in default_roles
    ]

    supabase_admin.table("roles").insert(roles_to_insert).execute()

    # Get org_admin role id
    role_resp = (
        supabase_admin
        .table("roles")
        .select("id")
        .eq("name", "org_admin")
        .eq("organization_id", org_id)
        .single()
        .execute()
    )

    if not role_resp.data:
        raise Exception("org_admin role not found")

    role_id = role_resp.data["id"]

    # Bootstrap the initial organization administrator through trusted onboarding.
    assign_onboarding_role(
        target_user_id=admin_id,
        role_name="org_admin",
        organization_id=org_id,
        actor_id=admin_id,
        reason="Initial organization administrator provisioned at registration",
    )

    emit_event(
        aggregate_type="organization",
        aggregate_id=org_id,
        event_type=EventTypes.ORGANIZATION_CREATED,
        payload={
            "organization_id": org_id,
            "admin_user_id": admin_id,
            "organization_name": org["name"],
            "admin_email": payload.admin_email,
        },
    )

    return {
        "message": "Organization registered successfully",
        "organization_id": org_id
    }


# ---------------------------------
# Update Organization Service
# ---------------------------------
def update_organization(
        org_id: str, 
        payload:OrganizationUpdate
        ):

    update_data = payload.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided")

    response = (
        supabase
        .table("organizations")
        .update(update_data)
        .eq("id", org_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Organization not found")

    return response.data[0]


# ----------------------------------
# Role Management Service
# ----------------------------------
def assign_user_role(
    role_data: RoleAssignment | dict,
    *,
    actor_id: str,
    actor_roles: list[dict],
):
    data = role_data.model_dump() if isinstance(role_data, RoleAssignment) else role_data
    return assign_organization_role(
        actor_id=actor_id,
        actor_roles=actor_roles,
        target_user_id=str(data["user_id"]),
        role_name=data["role_name"],
        organization_id=str(data["org_id"]),
        reason=data.get("reason"),
    )


# ----------------------------------
# Onboarding Invite Service
# ----------------------------------
def create_invitation(
        org_id: str, 
        email: str, 
        role_name: str, 
        invited_by: str,
        actor_roles: list[dict],
        actor_email: str,
        ):

    if email.strip().casefold() == actor_email.strip().casefold():
        raise HTTPException(status_code=403, detail="Users cannot invite themselves into a role")

    role_resp = (
        supabase_admin.table("roles")
        .select("id, name, role_type, organization_id, is_active")
        .eq("name", role_name.strip())
        .eq("organization_id", org_id)
        .maybe_single()
        .execute()
    )
    role = role_resp.data
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    authorize_role_change(
        actor_id=invited_by,
        actor_roles=actor_roles,
        target_user_id=f"invite:{email.strip().casefold()}",
        role_name=role["name"],
        role_type=role.get("role_type"),
        organization_id=org_id,
        role_organization_id=role.get("organization_id"),
        role_is_active=role.get("is_active") is True,
        action="assign",
    )

    token = str(uuid.uuid4())

    result = (
        supabase_admin
        .table("invitations")
        .insert({
            "email": email,
            "organization_id": org_id,
            "role_name": role_name,
            "invited_by": invited_by,
            "token": token,
            "expires_at": (datetime.utcnow() + timedelta(days=2)).isoformat()
        })
        .execute()
    )

    if not result.data:
        raise Exception("Failed to create invitation")

    # TODO: send email with token link
    # link = f"https://your-frontend.com/accept-invite?token={token}"

    return result.data[0]


# ---------------------------------
# Accept Invitation Service
# ---------------------------------
def accept_invitation(
        payload: AcceptInviteRequest
        ):

    # ---- Find invitation ----
    invite_resp = (
        supabase_admin
        .table("invitations")
        .select("*")
        .eq("token", payload.token)
        .eq("status", "pending")
        .maybe_single()
        .execute()
    )

    if not invite_resp.data:
        raise Exception("Invalid or expired invitation")

    invite = invite_resp.data

    expires_at = datetime.fromisoformat(invite["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) >= expires_at:
        raise HTTPException(status_code=400, detail="Invitation expired")

    issuer_id = str(invite["invited_by"])
    organization_id = str(invite["organization_id"])
    membership_rows = (
        supabase_admin.table("user_roles")
        .select("role_id")
        .eq("user_id", issuer_id)
        .eq("organization_id", organization_id)
        .eq("status", "active")
        .execute()
    ).data or []
    role_ids = [row["role_id"] for row in membership_rows if row.get("role_id")]
    if not role_ids:
        raise HTTPException(status_code=403, detail="Invitation issuer no longer has authority")
    issuer_roles = (
        supabase_admin.table("roles")
        .select("id, name, role_type, organization_id, is_active")
        .in_("id", role_ids)
        .execute()
    ).data or []
    issuer_assignments = [
        normalize_role_assignment(
            role_name=role["name"],
            role_type=role.get("role_type"),
            organization_id=organization_id,
            role_organization_id=role.get("organization_id"),
            role_is_active=role.get("is_active") is True,
        )
        for role in issuer_roles
    ]
    invite_role = (
        supabase_admin.table("roles")
        .select("id, name, role_type, organization_id, is_active")
        .eq("name", invite["role_name"])
        .eq("organization_id", organization_id)
        .maybe_single()
        .execute()
    ).data
    if not invite_role:
        raise HTTPException(status_code=404, detail="Invited role no longer exists")
    authorize_role_change(
        actor_id=issuer_id,
        actor_roles=issuer_assignments,
        target_user_id=f"invite:{invite['email'].strip().casefold()}",
        role_name=invite_role["name"],
        role_type=invite_role.get("role_type"),
        organization_id=organization_id,
        role_organization_id=invite_role.get("organization_id"),
        role_is_active=invite_role.get("is_active") is True,
        action="assign",
    )

    # ---- Create user in Supabase Auth ----
    res = supabase.auth.sign_up({
        "email": invite["email"],
        "password": payload.password
    })

    user = res.user

    if not user:
        raise Exception("Signup failed")

    assign_organization_role(
        actor_id=issuer_id,
        actor_roles=issuer_assignments,
        target_user_id=user.id,
        role_name=invite_role["name"],
        organization_id=organization_id,
        reason="Authorized organization invitation accepted",
    )

    # ---- Mark invitation accepted ----
    supabase_admin.table("invitations").update({
        "status": "accepted"
    }).eq("id", invite["id"]).execute()

    return {
        "message": "Account created successfully",
        "user_id": user.id
    }
