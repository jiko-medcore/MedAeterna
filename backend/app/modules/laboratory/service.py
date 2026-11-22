from fastapi import HTTPException

from app.core.security import require_patient_access
from app.core.supabase_admin import supabase_admin


def fetch_lab_record(lab_id: str) -> dict | None:
    response = (
        supabase_admin.table("lab_results")
        .select("*")
        .eq("id", lab_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def build_lab_detail(lab_id: str, current_user: dict) -> dict:
    lab = fetch_lab_record(lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab result not found")

    patient_id = lab.get("patient_id")
    if not patient_id:
        raise HTTPException(status_code=403, detail="Access denied")
    require_patient_access(str(patient_id), current_user)

    # Return a conservative, schema-tolerant projection.
    return {
        "id": lab.get("id"),
        "patient_id": lab.get("patient_id"),
        "status": lab.get("status"),
        "result": lab.get("result") or lab.get("results"),
        "metadata": {
            "performed_date": lab.get("performed_date") or lab.get("created_at"),
            "ordering_provider": lab.get("ordering_provider") or lab.get("clinician_id"),
            "facility_name": lab.get("facility_name"),
        },
        "raw": lab,
    }
