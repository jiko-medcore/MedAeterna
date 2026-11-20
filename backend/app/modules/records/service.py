from datetime import datetime

from fastapi import HTTPException

from app.core.security import require_patient_access
from app.core.supabase_client import supabase


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


def create_record(data, clinician_id: str):
    clinical_data = data.clinical_data or {}
    if data.record_type == "condition":
        clinical_data = normalize_condition_on_create(clinical_data)

    response = (
        supabase.table("medical_records")
        .insert(
            {
                "patient_id": str(data.patient_id),
                "clinician_id": clinician_id,
                "record_type": data.record_type,
                "clinical_data": clinical_data,
            }
        )
        .execute()
    )
    return (response.data or [None])[0]


def resolve_condition_record(record_id: str, current_user: dict) -> dict:
    records = (
        supabase.table("medical_records")
        .select("id, patient_id, clinical_data")
        .eq("id", record_id)
        .eq("record_type", "condition")
        .limit(1)
        .execute()
    ).data or []

    if not records:
        raise HTTPException(status_code=404, detail="Condition not found")

    record = records[0]
    require_patient_access(record["patient_id"], current_user)

    data = record.get("clinical_data") or {}
    data.setdefault("clinicalStatus", {}).setdefault("coding", [])
    data["clinicalStatus"]["coding"] = [
        {
            "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
            "code": "resolved",
            "display": "Resolved",
        }
    ]
    data["abatementDateTime"] = datetime.now().isoformat()

    update = (
        supabase.table("medical_records")
        .update({"clinical_data": data})
        .eq("id", record_id)
        .execute()
    )
    if not update.data:
        raise HTTPException(status_code=500, detail="Failed to update condition")
    return update.data[0]


def fetch_medical_records(patient_id: str):
    response = (
        supabase.table("medical_records")
        .select("*")
        .eq("patient_id", patient_id)
        .execute()
    )
    return response.data or []

