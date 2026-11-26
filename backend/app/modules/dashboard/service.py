from app.core.clinical_authorization import ensure_patient_self_read_context
from app.modules.patients.service import get_or_create_patient
from app.modules.prescriptions.service import get_active_prescriptions
from app.modules.reminders.service import get_upcoming_reminders


def build_user_summary(
    current_user: dict,
    *,
    prescriptions_authorized_context: dict | None = None,
    reminders_authorized_context: dict | None = None,
):
    patient_id = str(current_user.get("id") or "")

    # Validate both authorization decisions before any dashboard data access.
    ensure_patient_self_read_context(
        prescriptions_authorized_context,
        resource="clinical_record",
        patient_id=patient_id,
    )
    ensure_patient_self_read_context(
        reminders_authorized_context,
        resource="reminder",
        patient_id=patient_id,
    )

    result = get_or_create_patient(
        patient_id,
        current_user.get("email") or "",
    )
    patient = result["patient"]

    prescriptions = get_active_prescriptions(
        patient_id,
        authorized_context=prescriptions_authorized_context,
    )
    reminders = get_upcoming_reminders(
        patient_id,
        authorized_context=reminders_authorized_context,
    )

    full_name = " ".join(
        part
        for part in (
            patient.get("first_name"),
            patient.get("last_name"),
        )
        if part
    ) or None

    return {
        "user": {
            "fullName": full_name,
            "avatarUrl": patient.get("profile_image_url"),
        },
        "vitals": {
            "bloodGroup": patient.get("blood_group"),
            "genotype": patient.get("genotype"),
            "allergies": patient.get("allergies", []),
        },
        "activePrescriptions": prescriptions,
        "upcomingReminders": reminders,
    }
