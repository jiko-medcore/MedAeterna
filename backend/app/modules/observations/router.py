from fastapi import APIRouter, Depends, HTTPException

from app.core.security import (
    authorize_encounter_access,
    authorize_patient_access,
    get_current_user,
)
from app.core.supabase_admin import supabase_admin
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
    current_user: dict = Depends(get_current_user),
):
    authorize_patient_access(
        current_user,
        str(payload.patient_id),
        organization_id=str(payload.organization_id) if payload.organization_id else None,
    )
    return create_observation(payload=payload, created_by=current_user["id"])


@router.get("/patient/{patient_id}")
def get_patient_observations_endpoint(
    patient_id: str,
    current_user: dict = Depends(get_current_user),
):
    authorize_patient_access(current_user, str(patient_id))
    return get_patient_observations(patient_id)


@router.get("/encounter/{encounter_id}")
def get_encounter_observations_endpoint(
    encounter_id: str,
    current_user: dict = Depends(get_current_user),
):
    authorize_encounter_access(current_user, str(encounter_id))
    return get_encounter_observations(encounter_id)


@router.patch("/{observation_id}")
def update_observation_endpoint(
    observation_id: str,
    payload: ObservationUpdate,
    current_user: dict = Depends(get_current_user),
):
    obs = (
        supabase_admin.table("observations")
        .select("id, patient_id, organization_id")
        .eq("id", observation_id)
        .limit(1)
        .execute()
    )
    rows = obs.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Observation not found")

    row = rows[0]
    authorize_patient_access(
        current_user,
        str(row["patient_id"]),
        organization_id=str(row.get("organization_id") or "") or None,
    )
    return update_observation(observation_id=observation_id, payload=payload)



