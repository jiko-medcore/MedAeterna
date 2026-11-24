from app.core.supabase_client import supabase


#  ----- Service functions for prescriptions -----
def get_active_prescriptions(patient_id: str):
    response = (
        supabase
        .table("prescriptions")
        .select("id, patient_id, drug_name, category, dosage, instructions, start_date, end_date, status, created_at")
        .eq("patient_id", patient_id)
        .eq("status", "active")
        .execute()
    )

    return response.data or []
