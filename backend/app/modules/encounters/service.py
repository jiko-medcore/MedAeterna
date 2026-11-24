from fastapi import HTTPException
from app.core.clinical_authorization import CLINICAL_RECORD, ensure_authorized_context
from app.core.supabase_admin import supabase_admin

ENCOUNTER_LIST_SELECT = (
    "id, patient_id, organization_id, practitioner_id, encounter_class, status, "
    "reason, appointment_id, start_time, end_time, location, notes, created_at, updated_at"
)

# ---- Creare Encounter Service -----
def create_encounter(
    payload,
    created_by: str,
    *,
    authorized_context: dict,
):
    ensure_authorized_context(
        authorized_context,
        resource=CLINICAL_RECORD,
        action="create",
        patient_id=str(payload.patient_id),
        organization_id=str(payload.organization_id),
    )

    response = (
        supabase_admin
        .table("encounters")
        .insert({
            "patient_id": payload.patient_id,
            "organization_id": payload.organization_id,
            "practitioner_id": payload.practitioner_id,
            "encounter_class": payload.encounter_class,
            "status": payload.status,
            "reason": payload.reason,
            "appointment_id": payload.appointment_id,
            "start_time": (
                payload.start_time.isoformat()
                if payload.start_time else None
            ),
            "end_time": (
                payload.end_time.isoformat()
                if payload.end_time else None
            ),
            "location": payload.location,
            "notes": payload.notes,
            "metadata": payload.metadata,
            "created_by": created_by
        })
        .execute()
    )

    return response.data[0]


# ----- Get Patient Encounter Service -----
def get_patient_encounters(
    patient_id: str,
    *,
    authorized_context: dict,
):
    ensure_authorized_context(
        authorized_context,
        resource=CLINICAL_RECORD,
        action="read",
        patient_id=str(patient_id),
    )

    response = (
        supabase_admin
        .table("encounters")
        .select(f"""
            {ENCOUNTER_LIST_SELECT},
            organizations (
                id,
                name
            ),
            practitioners (
                id,
                first_name,
                last_name,
                photo
            )
        """)
        .eq("patient_id", patient_id)
        .order(
            "created_at",
            desc=True
        )
        .execute()
    )

    return response.data


# ----- Update Encounter Service -----
def update_encounter(
    encounter_id: str,
    payload,
    *,
    authorized_context: dict,
):
    ensure_authorized_context(
        authorized_context,
        resource=CLINICAL_RECORD,
        action="update",
        resource_id=str(encounter_id),
    )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    if (
        "start_time" in update_data
        and update_data["start_time"]
    ):
        update_data["start_time"] = (
            update_data["start_time"]
            .isoformat()
        )

    if (
        "end_time" in update_data
        and update_data["end_time"]
    ):
        update_data["end_time"] = (
            update_data["end_time"]
            .isoformat()
        )

    response = (
        supabase_admin
        .table("encounters")
        .update(update_data)
        .eq("id", encounter_id)
        .execute()
    )

    return response.data[0]