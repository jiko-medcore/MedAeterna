from app.core.clinical_authorization import CLINICAL_RECORD, ensure_authorized_context
from app.modules.records.service import fetch_medical_records


# ----- Get patient history -----
def get_patient_history(patient_id: str, *, authorized_context: dict):
    ensure_authorized_context(
        authorized_context,
        resource=CLINICAL_RECORD,
        action="read",
        patient_id=str(patient_id),
    )
    records = fetch_medical_records(
        str(patient_id),
        authorized_context=authorized_context,
    )

    formatted = []
    for record in records:
        formatted.append({
            "id": record["id"],
            "eventDate": record["created_at"],
            "facilityName": record.get("facility_name"),
            "providerName": record.get("provider_name"),
            "eventType": record.get("record_type"),
            "description": record.get("summary"),
        })

    return formatted
