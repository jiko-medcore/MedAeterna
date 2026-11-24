from app.core.supabase_client import supabase
from datetime import datetime


# ----- Reminder Service -----
def get_upcoming_reminders(patient_id: str):
    now = datetime.utcnow().isoformat()

    response = (
        supabase
        .table("reminders")
        .select("id, patient_id, title, description, reminder_date, status, created_at")
        .eq("patient_id", patient_id)
        .gte("reminder_date", now)
        .execute()
    )

    return response.data or []
