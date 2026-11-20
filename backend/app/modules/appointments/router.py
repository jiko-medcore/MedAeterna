from fastapi import APIRouter, Depends, HTTPException

from app.core.security import (
    authorize_patient_access,
    get_current_user,
    require_practitioner,
)
from app.core.supabase_admin import supabase_admin
from app.modules.appointments.schemas import AppointmentCreate, AppointmentUpdate
from app.modules.appointments.service import (
    create_appointment,
    get_patient_appointments,
    get_practitioner_appointments,
    update_appointment,
)


router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.post("/")
def create_new_appointment(
    payload: AppointmentCreate,
    current_user: dict = Depends(get_current_user),
):
    authorize_patient_access(
        current_user,
        str(payload.patient_id),
        organization_id=str(payload.organization_id) if payload.organization_id else None,
    )
    return create_appointment(payload=payload, created_by=current_user["id"])


@router.get("/patient/{patient_id}")
def get_appointments(
    patient_id: str,
    current_user: dict = Depends(get_current_user),
):
    authorize_patient_access(current_user, str(patient_id))
    return get_patient_appointments(patient_id)


@router.get("/practitioner/{practitioner_id}")
def request_practitioner_appointments(
    practitioner_id: str,
    current_user: dict = Depends(get_current_user),
    practitioner: dict = Depends(require_practitioner),
):
    # Practitioners may only view their own schedule unless broader admin policy
    # is explicitly implemented elsewhere.
    if str(practitioner.get("id")) != str(practitioner_id):
        raise HTTPException(status_code=403, detail="Access denied")
    return get_practitioner_appointments(practitioner_id)


@router.patch("/{appointment_id}")
def update_patient_appointment(
    appointment_id: str,
    payload: AppointmentUpdate,
    current_user: dict = Depends(get_current_user),
):
    appointment = (
        supabase_admin.table("appointments")
        .select("id, patient_id, organization_id")
        .eq("id", appointment_id)
        .limit(1)
        .execute()
    )
    rows = appointment.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Appointment not found")

    row = rows[0]
    authorize_patient_access(
        current_user,
        str(row["patient_id"]),
        organization_id=str(row.get("organization_id") or "") or None,
    )
    return update_appointment(appointment_id=appointment_id, payload=payload)
