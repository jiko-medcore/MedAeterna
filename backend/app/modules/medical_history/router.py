from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from .service import get_patient_history

router = APIRouter()


@router.get("/api/v1/medical-history")
def medical_history(current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_patient"):
        raise HTTPException(status_code=403, detail="Access denied")
    return {"data": get_patient_history(current_user["id"])}
