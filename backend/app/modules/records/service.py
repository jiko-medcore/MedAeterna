from datetime import datetime, timezone

from fastapi import HTTPException

from app.core.clinical_authorization import CLINICAL_RECORD, ensure_authorized_context
from app.core.supabase_admin import supabase_admin


def normalize_condition_on_create(data: dict) -> dict:
    if "clinicalStatus" not in data or not isinstance(data["clinicalStatus"], dict):
        data["clinicalStatus"] = {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    "code": "active",
                    "display": "Active",
                }
            ]
        }
    return data


def create_record(data, *, authorized_context: dict):
    """Create a legacy medical_records row only with a route-issued decision."""
    patient_id = str(data.patient_id)
    ensure_authorized_context(
        authorized_context,
        resource=CLINICAL_RECORD,
        action="create",
        patient_id=patient_id,
    )
    clinician_id = str(authorized_context["authorized_user_id"])
    clinical_data = data.clinical_data or {}
    if data.record_type == "condition":
        clinical_data = normalize_condition_on_create(clinical_data)

    response = (
        supabase_admin.table("medical_records")
        .insert(
            {
                "patient_id": patient_id,
                "clinician_id": clinician_id,
                "record_type": data.record_type,
                "clinical_data": clinical_data,
            }
        )
        .execute()
    )
    return (response.data or [None])[0]


def resolve_condition_record(
    record_id: str,
    *,
    authorized_context: dict,
) -> dict:
    """Resolve a stored condition after resource-id and patient scope authorization."""
    ensure_authorized_context(
        authorized_context,
        resource=CLINICAL_RECORD,
        action="update",
    )
    patient_id = str(authorized_context.get("authorized_patient_id") or "")
    ensure_authorized_context(
        authorized_context,
        resource=CLINICAL_RECORD,
        action="update",
        patient_id=patient_id,
        resource_id=str(record_id),
    )
    resource_row = authorized_context.get("resource_row")
    if (
        not isinstance(resource_row, dict)
        or str(resource_row.get("id") or "") != str(record_id)
        or str(resource_row.get("patient_id") or "") != patient_id
        or resource_row.get("record_type") != "condition"
    ):
        raise HTTPException(status_code=403, detail="Condition authorization context mismatch")

    records = (
        supabase_admin.table("medical_records")
        .select("id, patient_id, clinical_data")
        .eq("id", str(record_id))
        .eq("patient_id", patient_id)
        .eq("record_type", "condition")
        .limit(1)
        .execute()
    ).data or []

    if not records:
        raise HTTPException(status_code=404, detail="Condition not found")

    record = records[0]
    data = record.get("clinical_data") or {}
    data.setdefault("clinicalStatus", {}).setdefault("coding", [])
    data["clinicalStatus"]["coding"] = [
        {
            "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
            "code": "resolved",
            "display": "Resolved",
        }
    ]
    data["abatementDateTime"] = datetime.now(timezone.utc).isoformat()

    update = (
        supabase_admin.table("medical_records")
        .update({"clinical_data": data, "updated_by": authorized_context["authorized_user_id"]})
        .eq("id", str(record_id))
        .eq("patient_id", patient_id)
        .eq("record_type", "condition")
        .execute()
    )
    if not update.data:
        raise HTTPException(status_code=500, detail="Failed to update condition")
    return update.data[0]


def fetch_medical_records(
    patient_id: str,
    *,
    authorized_context: dict,
):
    """Return the minimal history projection after explicit patient-read authorization."""
    ensure_authorized_context(
        authorized_context,
        resource=CLINICAL_RECORD,
        action="read",
        patient_id=str(patient_id),
    )
    response = (
        supabase_admin.table("medical_records")
        .select("id, created_at, record_type")
        .eq("patient_id", str(patient_id))
        .execute()
    )
    return response.data or []
