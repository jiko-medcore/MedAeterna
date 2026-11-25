from fastapi import APIRouter, Depends, HTTPException

from app.core import security
from app.core.clinical_authorization import (
    APPOINTMENT,
    authorize_clinical_access,
    authorize_practitioner_schedule_access,
    authorize_table_access,
    practitioner_actor_id,
    resolve_practitioner_organization_id,
    require_patient_clinical,
)
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
    current_user: dict = Depends(security.get_current_user),
):
    practitioner_id = practitioner_actor_id(current_user)
    if payload.practitioner_id and str(payload.practitioner_id) != practitioner_id:
        raise HTTPException(
            status_code=403, detail="Appointments may only be created for the acting practitioner"
        )

    context = authorize_clinical_access(
        current_user,
        resource=APPOINTMENT,
        action="create",
        patient_id=str(payload.patient_id),
        organization_id=str(payload.organization_id),
        verified_conditions={"authorized_appointment_workflow"},
    )
    payload = payload.model_copy(update={"practitioner_id": practitioner_id})
    return create_appointment(
        payload=payload,
        created_by=current_user["id"],
        authorized_context=context,
    )


@router.get("/patient/{patient_id}")
def get_appointments(
    patient_id: str,
    context: dict = Depends(require_patient_clinical(APPOINTMENT, "read")),
):
    return get_patient_appointments(patient_id, authorized_context=context)


@router.get("/practitioner/{practitioner_id}")
def request_practitioner_appointments(
    practitioner_id: str,
    organization_id: str | None = None,
    current_user: dict = Depends(security.get_current_user),
):
    # Resolve organization selection against the authenticated practitioner's
    # validated role assignments, never the broader organization_ids field.
    resolved_org = resolve_practitioner_organization_id(
        current_user,
        str(organization_id) if organization_id is not None else None,
    )
    context = authorize_practitioner_schedule_access(
        current_user,
        practitioner_id=str(practitioner_id),
        organization_id=resolved_org,
    )
    return get_practitioner_appointments(
        str(context["authorized_practitioner_id"]),
        authorized_context=context,
    )


@router.patch("/{appointment_id}")
def update_patient_appointment(
    appointment_id: str,
    payload: AppointmentUpdate,
    current_user: dict = Depends(security.get_current_user),
):
    context = authorize_table_access(
        current_user,
        "appointments",
        appointment_id,
        "update",
        verified_conditions={"authorized_appointment_workflow"},
    )
    current_practitioner = context["resource_row"].get("practitioner_id")
    if payload.practitioner_id and str(payload.practitioner_id) != str(current_practitioner):
        raise HTTPException(
            status_code=403,
            detail="Practitioner reassignment requires an authorized workflow",
        )
    return update_appointment(
        appointment_id=appointment_id,
        payload=payload,
        authorized_context=context,
    )
