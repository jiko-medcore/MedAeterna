from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.consents.schemas import ConsentGrant, ConsentRevoke
from app.modules.consents.service import (
    get_patient_consents,
    grant_consent,
    revoke_consent,
)


router = APIRouter(prefix="/consents", tags=["Consents"])


def _require_patient_self(current_user: dict) -> str:
    if not current_user.get("is_patient"):
        raise HTTPException(status_code=403, detail="Access denied")
    return str(current_user["id"])


@router.post("/grant")
def create_consent(
    payload: ConsentGrant,
    current_user: dict = Depends(get_current_user),
):
    patient_id = _require_patient_self(current_user)
    return grant_consent(patient_id, payload, actor_user_id=str(current_user["id"]))


@router.post("/revoke")
def revoke_patient_consent(
    payload: ConsentRevoke,
    current_user: dict = Depends(get_current_user),
):
    patient_id = _require_patient_self(current_user)
    return revoke_consent(patient_id, payload, actor_user_id=str(current_user["id"]))


@router.get("/me")
def my_consents(current_user: dict = Depends(get_current_user)):
    patient_id = _require_patient_self(current_user)
    return get_patient_consents(patient_id)
