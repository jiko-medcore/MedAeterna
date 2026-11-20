from fastapi import APIRouter, Depends, HTTPException

from app.core.security import (
    authorize_encounter_access,
    authorize_patient_access,
    get_current_user,
)
from app.core.supabase_admin import supabase_admin
from app.modules.medications.schemas import (
    MedicationRequestCreate,
    MedicationRequestUpdate,
)
from app.modules.medications.service import (
    create_medication,
    get_encounter_medication,
    get_patient_medication,
    update_medication,
)


router = APIRouter(
    prefix="/medication-requests",
    tags=["Medication Requests"],
)


@router.post("/")
def create_new_medication(
    payload: MedicationRequestCreate,
    current_user: dict = Depends(get_current_user),
):
    authorize_patient_access(
        current_user,
        str(payload.patient_id),
        organization_id=str(payload.organization_id) if payload.organization_id else None,
    )
    return create_medication(payload=payload, created_by=current_user["id"])


@router.get("/patient/{patient_id}")
def get_medication(
    patient_id: str,
    current_user: dict = Depends(get_current_user),
):
    authorize_patient_access(current_user, str(patient_id))
    return get_patient_medication(patient_id)


@router.get("/encounter/{encounter_id}")
def get_patient_encounter_medication(
    encounter_id: str,
    current_user: dict = Depends(get_current_user),
):
    authorize_encounter_access(current_user, str(encounter_id))
    return get_encounter_medication(encounter_id)


@router.patch("/{medication_request_id}")
def update_medication_request_endpoint(
    medication_request_id: str,
    payload: MedicationRequestUpdate,
    current_user: dict = Depends(get_current_user),
):
    medication = (
        supabase_admin.table("medication_requests")
        .select("id, patient_id, organization_id")
        .eq("id", medication_request_id)
        .limit(1)
        .execute()
    )
    rows = medication.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Medication request not found")

    row = rows[0]
    authorize_patient_access(
        current_user,
        str(row["patient_id"]),
        organization_id=str(row.get("organization_id") or "") or None,
    )
    return update_medication(
        medication_request_id=medication_request_id,
        payload=payload,
    )
