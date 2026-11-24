from fastapi import HTTPException
from app.core.clinical_authorization import CLINICAL_RECORD, ensure_authorized_context
from app.core.supabase_admin import supabase_admin

CONDITION_LIST_SELECT = (
    "id, patient_id, encounter_id, organization_id, practitioner_id, code, display, "
    "clinical_status, verification_status, category, severity, onset_date, "
    "abatement_date, recorded_date, notes, created_at, updated_at"
)
CONDITION_DETAIL_SELECT = CONDITION_LIST_SELECT


# ----- Encounter Validation Service -----
def validate_encounter(
    encounter_id: str,
    patient_id: str
):

    res = (
        supabase_admin
        .table("encounters")
        .select("patient_id")
        .eq("id", encounter_id)
        .single()
        .execute()
    )

    if not res.data:
        raise HTTPException(
            404,
            "Encounter not found"
        )

    if res.data["patient_id"] != patient_id:
        raise HTTPException(
            400,
            "Encounter does not belong to patient"
        )
    

# ----- Create Observation Service -----
def create_condition(
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

    validate_encounter(
        payload.encounter_id,
        payload.patient_id
    )

    response = (
        supabase_admin
        .table("conditions")
        .insert({
            "patient_id": payload.patient_id,
            "encounter_id": payload.encounter_id,
            "organization_id": payload.organization_id,
            "practitioner_id": payload.practitioner_id,
            "code": payload.code,
            "display": payload.display,
            "clinical_status": payload.clinical_status,
            "verification_status": payload.verification_status,
            "category": payload.category,
            "severity": payload.severity,
            "onset_date": (
                payload.onset_date.isoformat()
                if payload.onset_date else None
            ),
            "abatement_date": (
                payload.abatement_date.isoformat()
                if payload.abatement_date else None
            ),
            "recorded_date": (
                payload.recorded_date.isoformat()
                if payload.recorded_date else None
            ),
            "notes": payload.notes,
            "metadata": payload.metadata,
            "created_by": created_by
        })
        .execute()
    )

    return response.data[0]


# ----- Get Patient Condition Service -----
def get_patient_conditions(
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
        .table("conditions")
        .select(f"""
            {CONDITION_LIST_SELECT},
            practitioners (
                id,
                first_name,
                last_name
            )
        """)
        .eq("patient_id", patient_id)
        .order(
            "recorded_date",
            desc=True
        )
        .execute()
    )

    return response.data


#  ---- Get Encounter Condition Service -----
def get_encounter_conditions(
    encounter_id: str,
    *,
    authorized_context: dict,
):
    ensure_authorized_context(
        authorized_context,
        resource=CLINICAL_RECORD,
        action="read",
        resource_id=str(encounter_id),
    )

    response = (
        supabase_admin
        .table("conditions")
        .select(CONDITION_DETAIL_SELECT)
        .eq("encounter_id", encounter_id)
        .execute()
    )

    return response.data


# ----- Update Existing Condition Service -----
def update_condition(
    condition_id: str,
    payload,
    *,
    authorized_context: dict,
):
    ensure_authorized_context(
        authorized_context,
        resource=CLINICAL_RECORD,
        action="update",
        resource_id=str(condition_id),
    )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    if (
        "abatement_date" in update_data
        and update_data["abatement_date"]
    ):
        update_data["abatement_date"] = (
            update_data["abatement_date"]
            .isoformat()
        )

    response = (
        supabase_admin
        .table("conditions")
        .update(update_data)
        .eq("id", condition_id)
        .execute()
    )

    return response.data[0]