# modules/dashboard/service.py

from app.modules.patients.service import get_or_create_patient
from app.modules.prescriptions.service import get_active_prescriptions
from app.modules.reminders.service import get_upcoming_reminders


# This function builds a summary of the user's health data, including their profile information, active prescriptions, and upcoming reminders. It retrieves the necessary data from the respective services and formats it into a structured response.
def build_user_summary(current_user: dict):

    result = get_or_create_patient(
        current_user["id"], current_user.get("email") or ""
    )
    patient = result["patient"]

    prescriptions = get_active_prescriptions(current_user["id"])
    reminders = get_upcoming_reminders(current_user["id"])

    full_name = " ".join(
        part for part in (
            patient.get("first_name"),
            patient.get("last_name"),
        ) if part
    ) or None

    return {
        "user": {
            "fullName": full_name,
            "avatarUrl": patient.get("profile_image_url")
        },
        "vitals": {
            "bloodGroup": patient.get("blood_group"),
            "genotype": patient.get("genotype"),
            "allergies": patient.get("allergies", [])
        },
        "activePrescriptions": prescriptions,
        "upcomingReminders": reminders
    }
