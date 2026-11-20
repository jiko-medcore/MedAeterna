from fastapi import HTTPException
from app.core.clinical_authorization import APPOINTMENT, ensure_authorized_context
from app.core.supabase_admin import supabase_admin


# ----- Validate Appointment Time Service -----
def validate_appointment_times(
    start_time,
    end_time
):

    if end_time <= start_time:
        raise HTTPException(
            400,
            "end_time must be after start_time"
        )
    

# ----- Check Practitioner Availblity Service -----
def validate_practitioner_availability(
    practitioner_id: str,
    start_time,
    end_time
):

    overlapping = (
        supabase_admin
        .table("appointments")
        .select("id")
        .eq("practitioner_id", practitioner_id)
        .in_(
            "status",
            [
                "booked",
                "arrived",
                "checked-in"
            ]
        )
        .lt("start_time", end_time.isoformat())
        .gt("end_time", start_time.isoformat())
        .execute()
    )

    if overlapping.data:
        raise HTTPException(
            400,
            "Practitioner unavailable"
        )
    

# ----- Create Appointment Service -----
def create_appointment(
    payload,
    created_by: str,
    *,
    authorized_context: dict,
):
    ensure_authorized_context(
        authorized_context,
        resource=APPOINTMENT,
        action="create",
        patient_id=str(payload.patient_id),
        organization_id=str(payload.organization_id),
    )

    validate_appointment_times(
        payload.start_time,
        payload.end_time
    )

    if payload.practitioner_id:

        validate_practitioner_availability(
            payload.practitioner_id,
            payload.start_time,
            payload.end_time
        )

    response = (
        supabase_admin
        .table("appointments")
        .insert({
            "patient_id": payload.patient_id,
            "organization_id": payload.organization_id,
            "practitioner_id": payload.practitioner_id,
            "appointment_type": payload.appointment_type,
            "status": payload.status,
            "start_time": (
                payload.start_time.isoformat()
            ),
            "end_time": (
                payload.end_time.isoformat()
            ),
            "reason": payload.reason,
            "location": payload.location,
            "notes": payload.notes,
            "metadata": payload.metadata,
            "created_by": created_by
        })
        .execute()
    )

    return response.data[0]



# ----- Get Patients Appointment Service -----
def get_patient_appointments(
    patient_id: str,
    *,
    authorized_context: dict,
):
    ensure_authorized_context(
        authorized_context,
        resource=APPOINTMENT,
        action="read",
        patient_id=str(patient_id),
    )

    response = (
        supabase_admin
        .table("appointments")
        .select("""
            *,
            practitioners (
                id,
                first_name,
                last_name,
                photo
            )
        """)
        .eq("patient_id", patient_id)
        .order(
            "start_time",
            desc=True
        )
        .execute()
    )

    return response.data


# ----- Get List Practitioners Appointments Service -----
def get_practitioner_appointments(
    practitioner_id: str,
    *,
    authorized_context: dict,
):
    ensure_authorized_context(
        authorized_context,
        resource=APPOINTMENT,
        action="read",
    )
    if str(authorized_context.get("authorized_practitioner_id") or "") != str(practitioner_id):
        raise HTTPException(status_code=403, detail="Practitioner scope mismatch")

    response = (
        supabase_admin
        .table("appointments")
        .select("""
            *,
            patients (
                id,
                first_name,
                last_name
            )
        """)
        .eq("practitioner_id", practitioner_id)
        .order(
            "start_time",
            desc=True
        )
        .execute()
    )

    return response.data



# ----- Update Appointment Service -----
def update_appointment(
    appointment_id: str,
    payload,
    *,
    authorized_context: dict,
):
    ensure_authorized_context(
        authorized_context,
        resource=APPOINTMENT,
        action="update",
        resource_id=str(appointment_id),
    )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    if (
        "start_time" in update_data
        and update_data["start_time"]
    ):
        update_data["start_time"] = (
            update_data["start_time"]
            .isoformat()
        )

    if (
        "end_time" in update_data
        and update_data["end_time"]
    ):
        update_data["end_time"] = (
            update_data["end_time"]
            .isoformat()
        )

    existing = (
        supabase_admin
        .table("appointments")
        .select("*")
        .eq("id", appointment_id)
        .single()
        .execute()
    )

    if not existing.data:
        raise HTTPException(
            404,
            "Appointment not found"
        )

    start_time = (
        update_data.get(
            "start_time",
            existing.data["start_time"]
        )
    )

    end_time = (
        update_data.get(
            "end_time",
            existing.data["end_time"]
        )
    )

    validate_appointment_times(
        start_time,
        end_time
    )

    response = (
        supabase_admin
        .table("appointments")
        .update(update_data)
        .eq("id", appointment_id)
        .execute()
    )

    return response.data[0]