from fastapi import HTTPException

from app.core.clinical_authorization import CLINICAL_RECORD, ensure_authorized_context
from app.core.supabase_admin import supabase_admin

LAB_DETAIL_SELECT = (
    "id, patient_id, status, result_data, performed_at, created_at, clinician_id"
)


def fetch_lab_detail(lab_id: str, patient_id: str) -> dict | None:
    """Fetch reviewed display fields for the exact authorized patient/result pair."""
    response = (
        supabase_admin.table("lab_results")
        .select(LAB_DETAIL_SELECT)
        .eq("id", str(lab_id))
        .eq("patient_id", str(patient_id))
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def build_lab_detail(lab_id: str, *, authorized_context: dict) -> dict:
    """Build a lab response only after route authorization of its stored scope."""
    ensure_authorized_context(
        authorized_context,
        resource=CLINICAL_RECORD,
        action="read",
    )
    patient_id = str(authorized_context.get("authorized_patient_id") or "")
    ensure_authorized_context(
        authorized_context,
        resource=CLINICAL_RECORD,
        action="read",
        patient_id=patient_id,
        resource_id=str(lab_id),
    )
    resource_row = authorized_context.get("resource_row")
    if (
        not isinstance(resource_row, dict)
        or str(resource_row.get("id") or "") != str(lab_id)
        or str(resource_row.get("patient_id") or "") != patient_id
    ):
        raise HTTPException(status_code=403, detail="Lab result authorization context mismatch")

    lab = fetch_lab_detail(str(lab_id), patient_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab result not found")

    # No full-row projection is returned. The detail query is constrained to
    # both the authorized resource id and the patient id resolved before auth.
    return {
        "id": lab.get("id"),
        "patient_id": lab.get("patient_id"),
        "status": lab.get("status"),
        "result": lab.get("result_data"),
        "metadata": {
            "performed_date": lab.get("performed_at") or lab.get("created_at"),
            "ordering_provider": lab.get("clinician_id"),
        },
    }
