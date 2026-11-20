from fastapi import HTTPException
from app.core.clinical_authorization import (
    CARE_TEAM,
    audit_clinical_write,
    ensure_authorized_context,
)
from app.core.supabase_admin import supabase_admin


# ----- Create Care Team Service -----
def create_care_team(
    payload,
    *,
    authorized_context: dict,
):
    ensure_authorized_context(
        authorized_context,
        resource=CARE_TEAM,
        action="create",
        patient_id=str(payload.patient_id),
        organization_id=str(payload.organization_id),
    )

    response = (
        supabase_admin
        .table("care_teams")
        .insert({
            "patient_id": payload.patient_id,
            "organization_id": payload.organization_id,
            "name": payload.name,
            "status": payload.status,
            "category": payload.category,
            "reason": payload.reason,
            "managing_organization_id": (
                payload.managing_organization_id
            ),
            "notes": payload.notes
        })
        .execute()
    )

    resource_id = str(response.data[0]["id"])
    audit_clinical_write(
        authorized_context,
        action="create",
        resource_type="care_team",
        resource_id=resource_id,
    )
    return response.data[0]


# ----- Add Practitioner to Care Team Service -----
def add_care_team_participant(
    care_team_id: str,
    payload,
    *,
    authorized_context: dict,
):
    ensure_authorized_context(
        authorized_context,
        resource=CARE_TEAM,
        action="update",
        resource_id=str(care_team_id),
    )

    existing = (
        supabase_admin
        .table("care_team_participants")
        .select("id")
        .eq("care_team_id", care_team_id)
        .eq("practitioner_id", payload.practitioner_id)
        .eq("role_code", payload.role_code)
        .execute()
    )

    if existing.data:
        raise HTTPException(
            status_code=400,
            detail="Participant already exists"
        )

    response = (
        supabase_admin
        .table("care_team_participants")
        .insert({
            "care_team_id": care_team_id,
            "practitioner_id": payload.practitioner_id,
            "role_code": payload.role_code,
            "responsibility": payload.responsibility,
            "start_date": (
                payload.start_date.isoformat()
                if payload.start_date else None
            ),
            "end_date": (
                payload.end_date.isoformat()
                if payload.end_date else None
            ),
            "metadata": payload.metadata,
            "active": True
        })
        .execute()
    )

    audit_clinical_write(
        authorized_context,
        action="add_participant",
        resource_type="care_team",
        resource_id=str(care_team_id),
    )
    return response.data[0]


# ----- Get Patients Care Team -----
def get_patient_care_teams(
    patient_id: str,
    *,
    authorized_context: dict,
):
    ensure_authorized_context(
        authorized_context,
        resource=CARE_TEAM,
        action="read",
        patient_id=str(patient_id),
    )

    response = (
        supabase_admin
        .table("care_teams")
        .select("""
            *,
            organizations (
                id,
                name
            ),
            care_team_participants (
                *,
                practitioners (
                    id,
                    first_name,
                    last_name,
                    photo
                )
            )
        """)
        .eq("patient_id", patient_id)
        .execute()
    )

    return response.data


# ----- Update Care Team Service -----
def update_care_team_participant(
    participant_id: str,
    payload,
    *,
    authorized_context: dict,
):
    ensure_authorized_context(
        authorized_context,
        resource=CARE_TEAM,
        action="update",
        resource_id=str(participant_id),
    )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    if (
        "start_date" in update_data
        and update_data["start_date"]
    ):
        update_data["start_date"] = (
            update_data["start_date"]
            .isoformat()
        )

    if (
        "end_date" in update_data
        and update_data["end_date"]
    ):
        update_data["end_date"] = (
            update_data["end_date"]
            .isoformat()
        )

    response = (
        supabase_admin
        .table("care_team_participants")
        .update(update_data)
        .eq("id", participant_id)
        .execute()
    )

    audit_clinical_write(
        authorized_context,
        action="update_participant",
        resource_type="care_team_participant",
        resource_id=str(participant_id),
    )
    return response.data[0]


# ----- Care Team Assignment Service ----
def assign_care_team(
    practitioner_id: str,
    payload,
    assigned_by: str,
    *,
    authorized_context: dict,
):
    ensure_authorized_context(
        authorized_context,
        resource=CARE_TEAM,
        action="administer",
        patient_id=str(payload.patient_id),
        organization_id=str(payload.organization_id),
    )

    existing = (
        supabase_admin
        .table("patient_care_team")
        .select("id")
        .eq("patient_id", payload.patient_id)
        .eq("practitioner_id", practitioner_id)
        .eq("organization_id", payload.organization_id)
        .execute()
    )

    if existing.data:
        raise HTTPException(
            status_code=400,
            detail="Already assigned"
        )

    response = (
        supabase_admin
        .table("patient_care_team")
        .insert({
            "patient_id": payload.patient_id,
            "practitioner_id": practitioner_id,
            "organization_id": payload.organization_id,
            "role": payload.role,
            "notes": payload.notes,
            "assigned_by": assigned_by,
            "start_date": (
                payload.start_date.isoformat()
                if payload.start_date else None
            ),
            "end_date": (
                payload.end_date.isoformat()
                if payload.end_date else None
            ),
            "metadata": payload.metadata,
            "active": True
        })
        .execute()
    )

    resource_id = str(response.data[0]["id"])
    audit_clinical_write(
        authorized_context,
        action="assign",
        resource_type="patient_care_team",
        resource_id=resource_id,
    )
    return response.data[0]
