from fastapi import HTTPException

from app.core.audit.actions import AuditActions
from app.core.audit.service import log_audit_event
from app.core.role_assignment_policy import (
    authorize_practitioner_role_change,
    authorize_practitioner_role_read,
)
from app.core.supabase_admin import supabase_admin


# ----- Practitioner Assignment Service -----
def assign_practitioner_role(
    *,
    actor_id: str,
    actor_roles: list[dict],
    target_practitioner_id: str,
    payload,
):
    organization_id = str(payload.organization_id)

    # SPEC-02 delegation: authorize before any privileged lookup or write.
    authorize_practitioner_role_change(
        actor_id=str(actor_id),
        actor_roles=actor_roles,
        target_practitioner_id=str(target_practitioner_id),
        organization_id=organization_id,
        action="assign",
    )

    practitioner = (
        supabase_admin
        .table("practitioners")
        .select("id")
        .eq("id", str(target_practitioner_id))
        .limit(1)
        .execute()
    ).data
    if not practitioner:
        raise HTTPException(status_code=404, detail="Practitioner not found")

    existing = (
        supabase_admin
        .table("practitioner_roles")
        .select("id")
        .eq("practitioner_id", str(target_practitioner_id))
        .eq("organization_id", organization_id)
        .eq("role_code", payload.role_code)
        .execute()
    )

    if existing.data:
        raise HTTPException(
            status_code=400,
            detail="Role already assigned"
        )

    # Fail closed: a failed audit write prevents the role assignment.
    log_audit_event(
        actor_id=str(actor_id),
        actor_type="user",
        action=AuditActions.PRACTITIONER_ROLE_ASSIGNED,
        resource_type="practitioner_role",
        resource_id=str(target_practitioner_id),
        organization_id=organization_id,
        metadata={"role_code": payload.role_code},
    )

    response = (
        supabase_admin
        .table("practitioner_roles")
        .insert({
            "practitioner_id": str(target_practitioner_id),
            "organization_id": organization_id,
            "role_code": payload.role_code,
            "specialty_code": payload.specialty_code,
            "department": payload.department,
            "permissions": payload.permissions,
            "start_date": (
                payload.start_date.isoformat()
                if payload.start_date else None
            ),
            "end_date": (
                payload.end_date.isoformat()
                if payload.end_date else None
            ),
            "active": True
        })
        .execute()
    )

    return response.data[0]


# ----- Get Practitioners Role Service -----
def get_my_practitioner_roles(
    practitioner_id: str
):

    response = (
        supabase_admin
        .table("practitioner_roles")
        .select(
            "id, organization_id, role_code, specialty_code, department, "
            "permissions, start_date, end_date, active, "
            "organizations (id, name, organization_type)"
        )
        .eq("practitioner_id", str(practitioner_id))
        .execute()
    )

    return response.data


# ----- Update Practitioners Role Service -----
def update_practitioner_role(
    *,
    actor_id: str,
    actor_roles: list[dict],
    role_id: str,
    payload,
):

    # Scope-resolution read: only the fields needed to authorize the target.
    role_rows = (
        supabase_admin
        .table("practitioner_roles")
        .select("id, organization_id, practitioner_id, role_code")
        .eq("id", str(role_id))
        .limit(1)
        .execute()
    ).data or []
    if not role_rows:
        raise HTTPException(status_code=404, detail="Practitioner role not found")
    role = role_rows[0]
    organization_id = str(role["organization_id"])

    authorize_practitioner_role_change(
        actor_id=str(actor_id),
        actor_roles=actor_roles,
        target_practitioner_id=str(role["practitioner_id"]),
        organization_id=organization_id,
        action="update",
    )

    update_data = payload.model_dump(exclude_unset=True)
    if "start_date" in update_data and update_data["start_date"]:
        update_data["start_date"] = update_data["start_date"].isoformat()
    if "end_date" in update_data and update_data["end_date"]:
        update_data["end_date"] = update_data["end_date"].isoformat()

    log_audit_event(
        actor_id=str(actor_id),
        actor_type="user",
        action=AuditActions.PRACTITIONER_ROLE_UPDATED,
        resource_type="practitioner_role",
        resource_id=str(role_id),
        organization_id=organization_id,
        metadata={"updated_fields": sorted(payload.model_fields_set)},
    )

    response = (
        supabase_admin
        .table("practitioner_roles")
        .update(update_data)
        .eq("id", str(role_id))
        .eq("organization_id", organization_id)
        .execute()
    )

    return response.data[0]


# ----- Get Practitioners organization Service -----
def get_organization_practitioners(
    *,
    actor_roles: list[dict],
    organization_id: str,
):
    # Listing includes practitioner contact data, so require org-admin authority.
    authorize_practitioner_role_read(
        actor_roles=actor_roles,
        organization_id=str(organization_id),
    )

    response = (
        supabase_admin
        .table("practitioner_roles")
        .select(
            "id, organization_id, practitioner_id, role_code, specialty_code, "
            "department, active, start_date, end_date, "
            "practitioners (id, first_name, last_name)"
        )
        .eq("organization_id", str(organization_id))
        .eq("active", True)
        .execute()
    )

    return response.data
