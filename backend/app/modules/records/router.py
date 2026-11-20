from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import (
    authorize_patient_access,
    authorize_permission,
    get_current_user,
)
from app.core.supabase_admin import supabase_admin
from app.modules.records.schemas import MedicalRecordCreate, MedicationInput
from app.modules.records.service import create_record, resolve_condition_record
from app.modules.terminology.constants import CODE_SYSTEMS

router = APIRouter(prefix="/records", tags=["Medical Records"])


def _authorize_record_write(current_user: dict, patient_id: str, permission_name: str) -> dict:
    authz = authorize_patient_access(current_user, str(patient_id))
    org_id = authz.get("authorized_organization_id")
    if not org_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return authorize_permission(authz, permission_name, str(org_id))


@router.post("/observations", status_code=201)
def create_observation(
    payload: MedicalRecordCreate,
    current_user: dict = Depends(get_current_user),
):
    current_user = _authorize_record_write(current_user, payload.patient_id, "create_observation")
    return create_record(payload, clinician_id=current_user["id"])


@router.post("/conditions", status_code=201)
def create_condition(
    payload: MedicalRecordCreate,
    current_user: dict = Depends(get_current_user),
):
    current_user = _authorize_record_write(current_user, payload.patient_id, "create_condition")
    return create_record(payload, clinician_id=current_user["id"])


@router.post("/medications", status_code=201)
def create_medication(
    payload: MedicationInput,
    current_user: dict = Depends(get_current_user),
):
    current_user = _authorize_record_write(current_user, payload.patient_id, "create_medication")
    fhir_medication = {
        "resourceType": "MedicationRequest",
        "status": "active",
        "intent": "order",
        "medicationCodeableConcept": {
            "coding": [
                {
                    "system": CODE_SYSTEMS["RXNORM"],
                    "code": payload.code,
                    "display": payload.display,
                }
            ]
        },
        "subject": {"reference": f"Patient/{payload.patient_id}"},
        "authoredOn": date.today().isoformat(),
    }
    if payload.dosage_text:
        fhir_medication["dosageInstruction"] = [{"text": payload.dosage_text}]

    record = MedicalRecordCreate(
        patient_id=payload.patient_id,
        record_type="medication",
        clinical_data=fhir_medication,
    )
    return create_record(record, clinician_id=current_user["id"])


@router.patch("/conditions/{record_id}/resolve")
def resolve_condition(
    record_id: str,
    current_user: dict = Depends(get_current_user),
):
    rows = (
        supabase_admin.table("medical_records")
        .select("id, patient_id, record_type")
        .eq("id", record_id)
        .eq("record_type", "condition")
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Condition not found")
    patient_id = str(rows[0]["patient_id"])
    current_user = _authorize_record_write(current_user, patient_id, "resolve_condition")
    return resolve_condition_record(record_id, current_user)
