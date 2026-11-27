from fastapi import APIRouter, Depends

from app.core.clinical_authorization import authorize_patient_self_read
from app.core.security import get_current_user
from .service import build_user_summary

router = APIRouter(prefix="/api/v1", tags=["Dashboard"])


@router.get("/user/summary")
def user_summary(current_user: dict = Depends(get_current_user)):
    patient_id = str(current_user.get("id") or "")

    prescriptions_context = authorize_patient_self_read(
        current_user,
        resource="clinical_record",
        patient_id=patient_id,
    )
    reminders_context = authorize_patient_self_read(
        current_user,
        resource="reminder",
        patient_id=patient_id,
    )

    return build_user_summary(
        current_user,
        prescriptions_authorized_context=prescriptions_context,
        reminders_authorized_context=reminders_context,
    )
