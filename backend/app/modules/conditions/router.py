from fastapi import APIRouter, Depends, HTTPException

from app.core.security import (
    authorize_encounter_access,
    authorize_patient_access,
    get_current_user,
)
from app.core.supabase_admin import supabase_admin
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
    current_user: dict = Depends(get_current_user),
):
    authorize_patient_access(
        current_user,
        str(payload.patient_id),
        organization_id=str(payload.organization_id) if payload.organization_id else None,
    )
    return create_condition(payload=payload, created_by=current_user["id"])


@router.get("/patient/{patient_id}")
def get_conditions(
    patient_id: str,
    current_user: dict = Depends(get_current_user),
):
    authorize_patient_access(current_user, str(patient_id))
    return get_patient_conditions(patient_id)


@router.get("/encounter/{encounter_id}")
def get_patient_encounter_condition(
    encounter_id: str,
    current_user: dict = Depends(get_current_user),
):
    authorize_encounter_access(current_user, str(encounter_id))
    return get_encounter_conditions(encounter_id)


@router.patch("/{condition_id}")
def update_patient_condition(
    condition_id: str,
    payload: ConditionUpdate,
    current_user: dict = Depends(get_current_user),
):
    condition = (
        supabase_admin.table("conditions")
        .select("id, patient_id, organization_id")
        .eq("id", condition_id)
        .limit(1)
        .execute()
    )
    rows = condition.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Condition not found")

    row = rows[0]
    authorize_patient_access(
        current_user,
        str(row["patient_id"]),
        organization_id=str(row.get("organization_id") or "") or None,
    )
    return update_condition(condition_id=condition_id, payload=payload)
