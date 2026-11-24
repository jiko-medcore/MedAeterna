from fastapi import HTTPException
from app.core.clinical_authorization import CLINICAL_RECORD, ensure_authorized_context
from app.core.supabase_admin import supabase_admin

MEDICATION_LIST_SELECT = (
    "id, patient_id, encounter_id, organization_id, practitioner_id, medication_code, "
    "medication_name, status, intent, dosage_instruction, route, frequency, quantity, "
    "duration, dispense_request, substitution_allowed, authored_on, notes, created_at, updated_at"
)
MEDICATION_DETAIL_SELECT = MEDICATION_LIST_SELECT


# ----- Validating Encounter -----
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
    

# ----- Create Medication Service -----
def create_medication(
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
        .table("medication_requests")
        .insert({
            "patient_id": payload.patient_id,
            "encounter_id": payload.encounter_id,
            "organization_id": payload.organization_id,
            "practitioner_id": payload.practitioner_id,
            "medication_code": payload.medication_code,
            "medication_name": payload.medication_name,
            "status": payload.status,
            "intent": payload.intent,
            "dosage_instruction": payload.dosage_instruction,
            "route": payload.route,
            "frequency": payload.frequency,
            "quantity": payload.quantity,
            "duration": payload.duration,
            "dispense_request": payload.dispense_request,
            "substitution_allowed": payload.substitution_allowed,
            "authored_on": (
                payload.authored_on.isoformat()
                if payload.authored_on else None
            ),
            "notes": payload.notes,
            "metadata": payload.metadata,
            "created_by": created_by
        })
        .execute()
    )

    return response.data[0]


# ----- Get Patient Medication Service -----
def get_patient_medication(
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
        .table("medication_requests")
        .select(f"""
            {MEDICATION_LIST_SELECT},
            practitioners (
                id,
                first_name,
                last_name
            )
        """)
        .eq("patient_id", patient_id)
        .order(
            "authored_on",
            desc=True
        )
        .execute()
    )

    return response.data


# ----- Get Encounter Medication Service ----- 
def get_encounter_medication(
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
        .table("medication_requests")
        .select(MEDICATION_DETAIL_SELECT)
        .eq("encounter_id", encounter_id)
        .execute()
    )

    return response.data


# ----- Update Medication Service -----
def update_medication(
    medication_request_id: str,
    payload,
    *,
    authorized_context: dict,
):
    ensure_authorized_context(
        authorized_context,
        resource=CLINICAL_RECORD,
        action="update",
        resource_id=str(medication_request_id),
    )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    response = (
        supabase_admin
        .table("medication_requests")
        .update(update_data)
        .eq("id", medication_request_id)
        .execute()
    )

    return response.data[0]