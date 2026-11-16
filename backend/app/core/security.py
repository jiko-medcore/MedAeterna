from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.supabase_client import supabase
from app.core.supabase_admin import supabase_admin
# from jose import jwt 
# from jose.exceptions import JWTError
from app.core.config import settings
from app.core.role_catalogue import (
    ORGANIZATION_ADMINISTRATOR,
    PATIENT,
    PRACTITIONER,
    SYSTEM_ADMINISTRATOR,
    has_scoped_category,
    normalize_role_assignment,
)
from fastapi import Depends, HTTPException
from app.modules.practitioners.service import (
    get_practitioner_by_id
)
from datetime import datetime, timezone
import logging


logger = logging.getLogger(__name__)


# ----- Security Dependencies -----
security = HTTPBearer()


# ----- Get Current User -----
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Validate Supabase JWT and resolve the user's identity.

    Authentication:
        - JWT validation uses the authenticated Supabase client.

    Identity Resolution:
        - Uses supabase_admin exclusively.
        - Independent of RLS.
        - Supports multiple roles.
        - Supports organization memberships.
    """

    # -----------------------------
    # Verify JWT
    # -----------------------------
    token = credentials.credentials

    try:
        response = supabase.auth.get_user(token)
        user = response.user
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        )

    # -----------------------------
    # Fetch user role assignments
    # -----------------------------
    role_rows = (
        supabase_admin
        .table("user_roles")
        .select("organization_id, role_id")
        .eq("user_id", user.id)
        .execute()
    ).data or []

    if not role_rows:
        raise HTTPException(
            status_code=403,
            detail="User has no assigned roles"
        )

    # -----------------------------
    # Fetch all referenced roles
    # -----------------------------
    role_ids = list({
        row["role_id"]
        for row in role_rows
            if row.get("role_id")
        })

    role_lookup_rows = (
        supabase_admin
        .table("roles")
        .select("id, name, role_type, organization_id, is_active")
        .in_("id", role_ids)
        .execute()
    ).data or []

    role_lookup = {
        role["id"]: role
        for role in role_lookup_rows
    }

    # -----------------------------
    # Build role objects
    # -----------------------------
    roles = []
    organization_ids = set()

    for assignment in role_rows:

        role_info = role_lookup.get(
            assignment["role_id"]
        )

        if not role_info:
            continue

        role_assignment = normalize_role_assignment(
            role_name=role_info["name"],
            role_type=role_info.get("role_type"),
            organization_id=assignment.get("organization_id"),
            role_organization_id=role_info.get("organization_id"),
            role_is_active=role_info.get("is_active"),
        )
        roles.append(role_assignment)

        if (
            role_assignment["category"] in {PRACTITIONER, ORGANIZATION_ADMINISTRATOR}
            and assignment.get("organization_id")
        ):
            organization_ids.add(
                assignment["organization_id"]
            )

    if not roles:
        raise HTTPException(
            status_code=403,
            detail="No valid roles found for user"
        )

    # Do not choose an arbitrary "primary" role. Legacy scalar role is only
    # populated when the user has exactly one recognized role assignment.
    legacy_role = (
        roles[0]["name"]
        if len(roles) == 1 and roles[0]["category"] != "unmapped"
        else None
    )

    is_patient = has_scoped_category(roles, PATIENT)
    is_practitioner = any(r["category"] == PRACTITIONER for r in roles)
    is_org_admin = any(r["category"] == ORGANIZATION_ADMINISTRATOR for r in roles)
    is_super_admin = has_scoped_category(roles, SYSTEM_ADMINISTRATOR)

    # -----------------------------
    # Return Current User
    # -----------------------------
    return {
        "id": user.id,
        "email": user.email,
        "role": legacy_role,
        "roles": roles,
        "organization_ids": list(organization_ids),
        "is_patient": is_patient,
        "is_practitioner": is_practitioner,
        "is_admin": is_super_admin,
        "is_org_admin": is_org_admin,
        "is_super_admin": is_super_admin,
    }


# ----- Role-Based Access Control -----
def require_role(required_role: str) -> callable:
    """
    Check for a recognized, global system role assignment.

    input: required_role (str)
    Returns: function that raises HTTPException if role is insufficient
    """
    def checker(user=Depends(get_current_user)):
        required_name = required_role.strip().casefold()
        has_system_role = any(
            role.get("name", "").strip().casefold() == required_name
            and role.get("role_type") == "system"
            and role.get("organization_id") is None
            and role.get("category") != "unmapped"
            for role in user.get("roles", [])
        )

        if not has_system_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )

        return user

    return checker


# ---- Get User Permissions -----
def get_user_permissions(user_id: str) -> set[str]:
    response = (
        supabase
        .rpc("get_user_permissions", {"uid": user_id})
        .execute()
    )

    return {p["permission"] for p in response.data}


# ----- Permission Guard Dependency -----
def require_permission(permission_name: str, org_id_param: str = "org_id"):
    def checker(
        request: Request,
        current_user=Depends(get_current_user)
    ):
        user_id = current_user["id"]

        # ---- Extract org_id dynamically from path ----
        org_id = request.path_params.get(org_id_param)

        if not org_id:
            raise HTTPException(400, "Organization context required")

        result = (
            supabase
            .table("user_roles")
            .select("""
                organization_id,
                roles!inner(
                    name,
                    role_permissions!inner(
                        permissions!inner(name)
                    )
                )
            """)
            .eq("user_id", user_id)
            .eq("organization_id", org_id)
            .execute()
        )

        if not result.data:
            raise HTTPException(403, "No roles in this organization")

        permissions = set()

        for row in result.data:
            role = row.get("roles")
            if not role:
                continue

            for rp in role.get("role_permissions", []):
                perm = rp.get("permissions")
                if perm:
                    permissions.add(perm.get("name"))

        if permission_name not in permissions:
            raise HTTPException(403, "Permission denied")

        return current_user

    return checker


# ----- Patient Access Dependency -----
def require_patient_access():

    def checker(
        patient_id: str,
        organization_id: str,
        user=Depends(get_current_user)
    ):

        consent = (
            supabase
            .table("consent_records")
            .select("*")
            .eq("patient_id", patient_id)
            .eq("organization_id", organization_id)
            .eq("status", "active")
            .execute()
        )

        if consent.data:
            return user

        care_team = (
            supabase
            .table("patient_care_team")
            .select("*")
            .eq("patient_id", patient_id)
            .eq("practitioner_id", user["id"])
            .eq("organization_id", organization_id)
            .eq("status", "active")
            .execute()
        )

        if care_team.data:
            return user

        raise HTTPException(
            status_code=403,
            detail="Patient access denied"
        )

    return checker
    

# ----- Organization Role Authorization -----
def require_org_role(required_role: str):

    def checker(
        organization_id: str,
        user=Depends(get_current_user)
    ):

        role = (
            supabase
            .table("practitioner_roles")
            .select("*")
            .eq("practitioner_id", user["id"])
            .eq("organization_id", organization_id)
            .eq("role_code", required_role)
            .eq("active", True)
            .execute()
        )

        if not role.data:
            raise HTTPException(
                status_code=403,
                detail="Organization access denied"
            )

        return user

    return checker


# ----- Require Practitoners Authorization -----
def require_practitioner(
    user=Depends(get_current_user)
):

    practitioner = get_practitioner_by_id(
        user["id"]
    )

    if not practitioner:
        raise HTTPException(
            status_code=403,
            detail="Practitioner account required"
        )

    return practitioner


# ----- Organization Role Authorization -----
def require_org_role(
    organization_id: str,
    allowed_roles: list[str] | None = None
):

    def dependency(
        practitioner=Depends(require_practitioner)
    ):

        query = (
            supabase_admin
            .table("practitioner_roles")
            .select("*")
            .eq("practitioner_id", practitioner["id"])
            .eq("organization_id", organization_id)
            .eq("active", True)
        )

        if allowed_roles:
            query = query.in_(
                "role_code",
                allowed_roles
            )

        response = query.execute()

        if not response.data:
            raise HTTPException(
                status_code=403,
                detail="Organization access denied"
            )

        return response.data[0]

    return dependency


# ----- Patient Access Authorizaton for Practitioners-----
def require_patient_access():

    def dependency(
        patient_id: str,
        organization_id: str,
        practitioner=Depends(require_practitioner)
    ):

        now = datetime.now(
            timezone.utc
        ).isoformat()

        # CHECK FOR CARE TEAM ACCESS
        care_team = (
            supabase_admin
            .table("patient_care_team")
            .select("*")
            .eq("patient_id", patient_id)
            .eq("organization_id", organization_id)
            .eq("practitioner_id", practitioner["id"])
            .eq("active", True)
            .execute()
        )

        if care_team.data:
            return practitioner

        # CHECK FOR CONSENT ACCESS
        consent = (
            supabase_admin
            .table("consent_records")
            .select("*")
            .eq("patient_id", patient_id)
            .eq("organization_id", organization_id)
            .eq("status", "active")
            .or_(
                f"""
                practitioner_id.eq.{practitioner["id"]},
                practitioner_id.is.null
                """
            )
            .execute()
        )

        if not consent.data:
            raise HTTPException(
                status_code=403,
                detail="Patient access denied"
            )

        valid_consents = []

        for item in consent.data:

            if (
                item.get("expires_at")
                and item["expires_at"] < now
            ):
                continue

            valid_consents.append(item)

        if not valid_consents:
            raise HTTPException(
                status_code=403,
                detail="Consent expired"
            )

        return practitioner

    return dependency
