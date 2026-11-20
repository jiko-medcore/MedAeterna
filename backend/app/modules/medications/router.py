from fastapi import APIRouter, Depends, HTTPException

from app.core import security
from app.core.clinical_authorization import (
    CLINICAL_RECORD,
    authorize_clinical_access,
    require_encounter_clinical,
    require_patient_clinical,
    require_table_clinical,
)
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
    current_user: dict = Depends(security.get_current_user),
):
    # Resolve encounter->patient/org from stored data before authorizing.
    encounter = security.fetch_resource(
        "encounters",
        "id, patient_id, organization_id",
        id=str(payload.encounter_id),
    )
    if not encounter:
        raise HTTPException(status_code=404, detail="Encounter not found")
    if str(encounter.get("patient_id")) != str(payload.patient_id):
        raise HTTPException(
            status_code=400, detail="Encounter does not belong to patient"
        )
    if encounter.get("organization_id") and str(encounter["organization_id"]) != str(
        payload.organization_id
    ):
        raise HTTPException(
            status_code=400, detail="Encounter organization does not match request"
        )

    context = authorize_clinical_access(
        current_user,
        resource=CLINICAL_RECORD,
        action="create",
        patient_id=str(payload.patient_id),
        organization_id=str(payload.organization_id),
        verified_conditions={"clinical_workflow"},
    )
    return create_medication(
        payload=payload,
        created_by=current_user["id"],
        authorized_context=context,
    )


@router.get("/patient/{patient_id}")
def get_medication(
    patient_id: str,
    context: dict = Depends(require_patient_clinical(CLINICAL_RECORD, "read")),
):
    return get_patient_medication(patient_id, authorized_context=context)


@router.get("/encounter/{encounter_id}")
def get_patient_encounter_medication(
    encounter_id: str,
    context: dict = Depends(require_encounter_clinical(CLINICAL_RECORD, "read")),
):
    # Encounter identity, patient and organization were resolved and authorized
    # before this handler ran; no service query happens on a denied request.
    return get_encounter_medication(encounter_id, authorized_context=context)


@router.patch("/{medication_request_id}")
def update_medication_request_endpoint(
    medication_request_id: str,
    payload: MedicationRequestUpdate,
    context: dict = Depends(
        require_table_clinical(
            "medication_requests",
            "medication_request_id",
            "update",
            # The update schema excludes patient/encounter/organization fields.
            verified_conditions={"clinical_workflow"},
        )
    ),
):
    return update_medication(
        medication_request_id=medication_request_id,
        payload=payload,
        authorized_context=context,
    )
