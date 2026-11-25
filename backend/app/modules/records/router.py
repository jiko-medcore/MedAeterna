from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.core.clinical_authorization import (
    CLINICAL_RECORD,
    authorize_clinical_access,
    authorize_table_access,
)
from app.core.security import authorize_permission, get_current_user
from app.modules.records.schemas import MedicalRecordCreate, MedicationInput
from app.modules.records.service import create_record, resolve_condition_record
from app.modules.terminology.constants import CODE_SYSTEMS

router = APIRouter(prefix="/records", tags=["Medical Records"])


def _authorize_record_write(
    current_user: dict, patient_id: str, permission_name: str,
    resource_family: str, action: str = "create",
) -> dict:
    authz = authorize_clinical_access(
        current_user,
        resource=CLINICAL_RECORD,
        action=action,
        patient_id=str(patient_id),
        relationship_resource_family=resource_family,
    )
    org_id = authz.get("authorized_organization_id")
    if not org_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return authorize_permission(authz, permission_name, str(org_id))


@router.post("/observations", status_code=201)
def create_observation(
    payload: MedicalRecordCreate,
    current_user: dict = Depends(get_current_user),
):
    current_user = _authorize_record_write(current_user, payload.patient_id, "create_observation", "observation")
    return create_record(payload, authorized_context=current_user)


@router.post("/conditions", status_code=201)
def create_condition(
    payload: MedicalRecordCreate,
    current_user: dict = Depends(get_current_user),
):
    current_user = _authorize_record_write(current_user, payload.patient_id, "create_condition", "condition")
    return create_record(payload, authorized_context=current_user)


@router.post("/medications", status_code=201)
def create_medication(
    payload: MedicationInput,
    current_user: dict = Depends(get_current_user),
):
    current_user = _authorize_record_write(current_user, payload.patient_id, "create_medication", "prescription")
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
    return create_record(record, authorized_context=current_user)


@router.patch("/conditions/{record_id}/resolve")
def resolve_condition(
    record_id: str,
    current_user: dict = Depends(get_current_user),
):
    context = authorize_table_access(
        current_user,
        "medical_records",
        str(record_id),
        "update",
        relationship_resource_family="condition",
    )
    if context.get("resource_row", {}).get("record_type") != "condition":
        raise HTTPException(status_code=404, detail="Condition not found")
    organization_id = str(context.get("authorized_organization_id") or "")
    if not organization_id:
        raise HTTPException(status_code=403, detail="Organization context required")
    context = authorize_permission(context, "resolve_condition", organization_id)
    return resolve_condition_record(
        str(record_id),
        authorized_context=context,
    )
