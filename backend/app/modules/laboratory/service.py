from fastapi import HTTPException

from app.core.security import require_patient_access
from app.core.supabase_admin import supabase_admin

LAB_SCOPE_SELECT = "id, patient_id"
LAB_DETAIL_SELECT = (
    "id, patient_id, status, result, results, performed_date, created_at, "
    "ordering_provider, clinician_id, facility_name"
)


def fetch_lab_scope(lab_id: str) -> dict | None:
    """Fetch only the ownership field needed to authorize a lab detail read."""
    response = (
        supabase_admin.table("lab_results")
        .select(LAB_SCOPE_SELECT)
        .eq("id", lab_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def fetch_lab_detail(lab_id: str) -> dict | None:
    """Fetch only approved display fields after patient access is authorized."""
    response = (
        supabase_admin.table("lab_results")
        .select(LAB_DETAIL_SELECT)
        .eq("id", lab_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def build_lab_detail(lab_id: str, current_user: dict) -> dict:
    scope = fetch_lab_scope(lab_id)
    if not scope:
        raise HTTPException(status_code=404, detail="Lab result not found")

    patient_id = scope.get("patient_id")
    if not patient_id:
        raise HTTPException(status_code=403, detail="Access denied")
    require_patient_access(str(patient_id), current_user)

    lab = fetch_lab_detail(lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab result not found")

    # No `raw` full-row projection: only reviewed clinical/display fields leave
    # this service, and only after the patient-access check above.
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
    }
