from fastapi import APIRouter, Depends, HTTPException

from app.core import security
from app.core.clinical_authorization import (
    CLINICAL_RECORD,
    authorize_clinical_access,
    require_encounter_clinical,
    require_patient_clinical,
    require_table_clinical,
)
from app.modules.observations.schemas import ObservationCreate, ObservationUpdate
from app.modules.observations.service import (
    create_observation,
    get_encounter_observations,
    get_patient_observations,
    update_observation,
)


router = APIRouter(prefix="/observations", tags=["Observations"])


@router.post("/")
def create_observation_endpoint(
    payload: ObservationCreate,
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
    return create_observation(
        payload=payload,
        created_by=current_user["id"],
        authorized_context=context,
    )


@router.get("/patient/{patient_id}")
def get_patient_observations_endpoint(
    patient_id: str,
    context: dict = Depends(require_patient_clinical(CLINICAL_RECORD, "read")),
):
    return get_patient_observations(patient_id, authorized_context=context)


@router.get("/encounter/{encounter_id}")
def get_encounter_observations_endpoint(
    encounter_id: str,
    context: dict = Depends(require_encounter_clinical(CLINICAL_RECORD, "read")),
):
    return get_encounter_observations(encounter_id, authorized_context=context)


@router.patch("/{observation_id}")
def update_observation_endpoint(
    observation_id: str,
    payload: ObservationUpdate,
    context: dict = Depends(
        require_table_clinical(
            "observations",
            "observation_id",
            "update",
            # Update schema excludes patient/encounter/organization identity.
            verified_conditions={"clinical_workflow"},
        )
    ),
):
    return update_observation(
        observation_id=observation_id,
        payload=payload,
        authorized_context=context,
    )
