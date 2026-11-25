from fastapi import APIRouter, Depends

from app.core.clinical_authorization import CLINICAL_RECORD, authorize_clinical_access
from app.core.security import get_current_user
from .service import get_patient_history

router = APIRouter()


@router.get("/api/v1/medical-history")
def medical_history(current_user: dict = Depends(get_current_user)):
    context = authorize_clinical_access(
        current_user,
        resource=CLINICAL_RECORD,
        action="read",
        patient_id=str(current_user.get("id") or ""),
    )
    return {"data": get_patient_history(
        str(context["authorized_patient_id"]),
        authorized_context=context,
    )}
