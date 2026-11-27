from typing import Any

from app.core.clinical_authorization import ensure_patient_self_read_context
from app.core.supabase_client import supabase


def get_active_prescriptions(
    patient_id: str,
    *,
    authorized_context: dict[str, Any] | None = None,
):
    ensure_patient_self_read_context(
        authorized_context,
        resource="clinical_record",
        patient_id=patient_id,
    )

    response = (
        supabase
        .table("prescriptions")
        .select(
            "id, patient_id, drug_name, category, dosage, instructions, "
            "start_date, end_date, status, created_at"
        )
        .eq("patient_id", patient_id)
        .eq("status", "active")
        .execute()
    )

    return response.data or []
