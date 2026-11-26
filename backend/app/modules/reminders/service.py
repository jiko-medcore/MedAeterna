from datetime import datetime, timezone
from typing import Any

from app.core.clinical_authorization import ensure_patient_self_read_context
from app.core.supabase_client import supabase


def get_upcoming_reminders(
    patient_id: str,
    *,
    authorized_context: dict[str, Any] | None = None,
):
    ensure_patient_self_read_context(
        authorized_context,
        resource="reminder",
        patient_id=patient_id,
    )

    now = datetime.now(timezone.utc).isoformat()

    response = (
        supabase
        .table("reminders")
        .select(
            "id, patient_id, title, description, reminder_date, status, created_at"
        )
        .eq("patient_id", patient_id)
        .gte("reminder_date", now)
        .execute()
    )

    return response.data or []
