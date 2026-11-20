from fastapi import APIRouter, Depends, HTTPException

from app.core import security
from app.core.clinical_authorization import (
    CLINICAL_RECORD,
    authorize_clinical_access,
    require_encounter_clinical,
    require_patient_clinical,
    require_table_clinical,
)
from app.modules.conditions.schemas import ConditionCreate, ConditionUpdate
from app.modules.conditions.service import (
    create_condition,
    get_encounter_conditions,
    get_patient_conditions,
    update_condition,
)


router = APIRouter(prefix="/conditions", tags=["Conditions"])


@router.post("/")
def create_new_condition(
    payload: ConditionCreate,
    current_user: dict = Depends(security.get_current_user),
):
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
            status_code=400,
            detail="Encounter organization does not match request",
        )

    context = authorize_clinical_access(
        current_user,
        resource=CLINICAL_RECORD,
        action="create",
        patient_id=str(payload.patient_id),
        organization_id=str(payload.organization_id),
        verified_conditions={"clinical_workflow"},
    )
    return create_condition(
        payload=payload,
        created_by=current_user["id"],
        authorized_context=context,
    )


@router.get("/patient/{patient_id}")
def get_conditions(
    patient_id: str,
    context: dict = Depends(require_patient_clinical(CLINICAL_RECORD, "read")),
):
    return get_patient_conditions(patient_id, authorized_context=context)


@router.get("/encounter/{encounter_id}")
def get_patient_encounter_condition(
    encounter_id: str,
    context: dict = Depends(require_encounter_clinical(CLINICAL_RECORD, "read")),
):
    return get_encounter_conditions(encounter_id, authorized_context=context)


@router.patch("/{condition_id}")
def update_patient_condition(
    condition_id: str,
    payload: ConditionUpdate,
    context: dict = Depends(
        require_table_clinical(
            "conditions",
            "condition_id",
            "update",
            # Update schema excludes patient/encounter/organization identity.
            verified_conditions={"clinical_workflow"},
        )
    ),
):
    return update_condition(
        condition_id=condition_id,
        payload=payload,
        authorized_context=context,
    )
