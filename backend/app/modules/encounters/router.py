from fastapi import APIRouter, Depends, HTTPException

from app.core.security import (
    authorize_encounter_access,
    authorize_patient_access,
    get_current_user,
    require_patient_access,
)
from app.core.supabase_admin import supabase_admin
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
    current_user: dict = Depends(get_current_user),
):
    authorize_patient_access(
        current_user,
        str(payload.patient_id),
        organization_id=str(payload.organization_id) if payload.organization_id else None,
    )
    return create_encounter(payload, current_user["id"])


@router.get("/patient/{patient_id}")
def patient_encounters(
    patient_id: str,
    organization_id: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    authorize_patient_access(
        current_user,
        str(patient_id),
        organization_id=str(organization_id) if organization_id else None,
    )
    return get_patient_encounters(patient_id)


@router.patch("/{encounter_id}")
def patch_encounter(
    encounter_id: str,
    payload: EncounterUpdate,
    current_user: dict = Depends(get_current_user),
):
    # Authorize against the target encounter's patient/org before update.
    authorize_encounter_access(current_user, str(encounter_id))
    return update_encounter(encounter_id, payload)
