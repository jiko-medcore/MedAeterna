from fastapi import APIRouter, Depends, HTTPException

from app.core import security
from app.core.clinical_authorization import (
    CLINICAL_RECORD,
    authorize_clinical_access,
    bind_clinical_actor,
    require_patient_clinical,
    require_table_clinical,
)
from app.modules.encounters.schemas import EncounterCreate, EncounterUpdate
from app.modules.encounters.service import (
    create_encounter,
    get_patient_encounters,
    update_encounter,
)


router = APIRouter(prefix="/encounters", tags=["Encounters"])


@router.post("/")
def create_new_encounter(
    payload: EncounterCreate,
    current_user: dict = Depends(security.get_current_user),
):
    if payload.appointment_id:
        appointment = security.fetch_resource(
            "appointments",
            "id, patient_id, organization_id",
            id=str(payload.appointment_id),
        )
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")
        if str(appointment.get("patient_id")) != str(payload.patient_id):
            raise HTTPException(
                status_code=400, detail="Appointment does not belong to patient"
            )
        if appointment.get("organization_id") and str(
            appointment["organization_id"]
        ) != str(payload.organization_id):
            raise HTTPException(
                status_code=400,
                detail="Appointment organization does not match request",
            )

    context = authorize_clinical_access(
        current_user,
        resource=CLINICAL_RECORD,
        action="create",
        patient_id=str(payload.patient_id),
        organization_id=str(payload.organization_id),
        verified_conditions={"clinical_workflow"},
    )
    payload = bind_clinical_actor(payload, context)
    return create_encounter(payload, current_user["id"], authorized_context=context)


@router.get("/patient/{patient_id}")
def patient_encounters(
    patient_id: str,
    organization_id: str | None = None,
    context: dict = Depends(require_patient_clinical(CLINICAL_RECORD, "read")),
):
    return get_patient_encounters(patient_id, authorized_context=context)


@router.patch("/{encounter_id}")
def patch_encounter(
    encounter_id: str,
    payload: EncounterUpdate,
    context: dict = Depends(
        require_table_clinical(
            "encounters",
            "encounter_id",
            "update",
            # Update schema excludes patient/organization/appointment identity.
            verified_conditions={"clinical_workflow"},
        )
    ),
):
    return update_encounter(encounter_id, payload, authorized_context=context)
