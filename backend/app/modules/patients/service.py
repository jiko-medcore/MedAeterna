from app.core.supabase_client import supabase
from app.core.supabase_admin import supabase_admin
from app.shared.utils.timeline_event_trans_helper import transform_record_to_event
from app.core.events.emitter import emit_event
from app.core.events.schemas import EventTypes
from uuid import UUID
from typing import List, Dict, Any
from app.modules.patients.exceptions import (
    PatientCreationError,
    PatientError,
    PatientNotFoundError,
    PatientUpdateError,
    ClinicianAssignmentError
)
from app.core.audit.service import log_audit_event
from app.core.audit.actions import AuditActions
import logging


logger = logging.getLogger(__name__)


# ----- Get Patient Summary -----
def get_patient_summary(patient_id: str) -> Dict[str, Any]:
    """
    Generate a summary of the patient's health data including 
    vitals, conditions, and medications.  

    input: patient_id (str) - unique identifier for the patient
    return: dict - summary of patient's health data
    """
    # ---- Fetch patient ----
    patient_resp = (
        supabase
        .table("patients")
        .select("*")
        .eq("id", patient_id)
        .execute()
    )

    if not patient_resp.data:
        raise PatientNotFoundError(
        f"Patient {patient_id} not found"
    )

    patient = patient_resp.data[0]

    # ---- Fetch all medical records ----
    records_resp = (
        supabase
        .table("medical_records")
        .select("*")
        .eq("patient_id", patient_id)
        .order("created_at", desc=True)
        .execute()
    )

    records = records_resp.data or []

    observations = []
    conditions = []
    medications = []

    for r in records:
        if r["record_type"] == "observation":
            observations.append(r)
        elif r["record_type"] == "condition":
            conditions.append(r)
        elif r["record_type"] == "medication":
            medications.append(r)

    # ---- Extract vitals (latest only) ----
    vitals = {}
    if observations:
        latest_obs = observations[0]["clinical_data"]
        vitals = {
            "name": latest_obs.get("code", {}).get("text"),
            "value": latest_obs.get("valueQuantity", {}).get("value"),
            "unit": latest_obs.get("valueQuantity", {}).get("unit"),
            "recorded_at": observations[0]["created_at"]
        }

    # ---- Extract conditions ----
    condition_set = set()

    for c in conditions:
        cd = c["clinical_data"]
        clinical_status = cd.get("clinicalStatus")

        if isinstance(clinical_status, dict):
            status = (
                clinical_status
                .get("coding", [{}])[0]
                .get("code")
            )
        elif isinstance(clinical_status, str):
            status = clinical_status
        else:
            status = None

        if status == "active":
            name = cd.get("code", {}).get("text")
            if name:
                condition_set.add(name)

    condition_list = list(condition_set)


    # ---- Extract medications ----
    medication_list = []
    for m in medications:
        cd = m["clinical_data"]
        medication_concept = (
            cd.get("medicationCodeableConcept", {})
        )

        coding = medication_concept.get(
            "coding",
            [{}]
        )

        medication_list.append({
            "name": coding[0].get("display"),
            "authored_on": cd.get("authoredOn")
        })

    # ---- Build summary ----
    summary = {
        "patient": {
            "id": patient["id"],
            "first_name": patient.get("first_name"),
            "last_name": patient.get("last_name"),
            "gender": patient.get("gender"),
            "date_of_birth": patient.get("date_of_birth")
        },
        "vitals": vitals,
        "conditions": condition_list,
        "medications": medication_list,
        "last_updated": records[0]["created_at"] if records else None
    }

    return summary


# ----- Get or Create Patient -----
def get_or_create_patient(
        user_id: str,
        email: str):
    response = (
        supabase
        .table("patients")
        .select("*")
        .eq("id", user_id)
        .execute()
    )

    if response.data:
        return {
            "patient": response.data[0],
            "created": False
        }

    # log Paitent data
    logger.info(f"PATIENT INSERT PAYLOAD: {user_id}")
    print(f"PATIENT INSERT PAYLOAD: {user_id}")


    # Insert Patient data
    insert = (
        supabase_admin
        .table("patients")
        .insert({
            "id": user_id,
            "email": email,
            "fhir_metadata": {
                "resourceType": "Patient"
            }
        })
        .execute()
    )

    # Verify Insertions of Pateint data
    verify = (
        supabase_admin
        .table("patients")
        .select("id,email,medical_id")
        .eq("id", user_id)
        .execute()
    )

    logger.info(f"VERIFY PATIENT: {verify.data}")

    if not insert.data:
        logger.error(f"INSERT FAILED: {insert}")
        raise PatientCreationError(
            f"Patient insert failed: {insert}"
        )

    logger.info(
        f"Creating patient for user {user_id}"
    )
    
    patient = insert.data[0]
    
    patient_id = str(patient.get("id", ""))

    logger.info(
        f"Creating Patient Insert: {patient_id}"
    )

    print(f"Creating Patient Insert: {patient_id}")

    if not patient_id:
        raise Exception("Failed to get patient ID from insert response")
    
    emit_event(
        aggregate_type="patient",
        aggregate_id=patient_id,
        event_type=EventTypes.PATIENT_CREATED,
        payload={
            "email": email
        }
    )

    # Log Sucessful Patient Creation
    log_audit_event(
        actor_id=user_id,
        actor_type="patient",
        action=AuditActions.PATIENT_CREATED,
        resource_type="patient",
        resource_id=patient_id
    )

    return {
        "patient": patient,
        "created": True
    }


# ----- Get Patient with Records -----
def get_patient_with_records(patient_id: str):
    patient = (
        supabase
        .table("patients")
        .select("*")
        .eq("id", patient_id)
        .execute()
    )

    patient= patient.data[0]

    records = (
        supabase
        .table("medical_records")
        .select("clinical_data")
        .eq("patient_id", patient_id)
        .execute()
    ).data

    return patient, records


# ----- Transform Record to Timeline Event -----
def build_patient_timeline(patient_id: UUID):
    """
    Build a chronological timeline of a patient's medical events.
    
    input: patient_id (UUID) - unique identifier for the patient
    return: dict - timeline of medical events
    """
    response = (
        supabase
        .table("medical_records")
        .select("*")
        .eq("patient_id", str(patient_id))
        .order("created_at", desc=True)
        .execute()
    )

    records = response.data or []

    events = []
    for record in records:
        event= transform_record_to_event(record)
        if event:
            events.append(event)
    

    events.sort(key=lambda e: e["date"], reverse=True)

    return {
        "patient_id": str(patient_id),
        "events": events
    }


# ----- Build Condition Resource -----
def build_condition_resource(payload: dict):
    """
    Build a FHIR Condition resource from a payload.
    Normalizes clinicalStatus and maps code.
    
    input: payload (dict) - condition data
    return: dict - FHIR Condition resource
    """
    return {
        "resourceType": "Condition",
        "clinicalStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    "code": payload.get("status", "active"),
                    "display": payload.get("status", "active").title()
                }
            ]
        },
        "code": payload["code"],
        "onsetDateTime": payload.get("onsetDateTime")
    }


# ---- Assign Clinician to Patient ----
def assign_clinician_to_patient(
    clinician_id: str,
    patient_id: str,
    role: str,
    assigned_by: str
):
    response = (
        supabase
        .table("clinicians_patients")
        .upsert({
            "clinician_id": clinician_id,
            "patient_id": patient_id,
            "role": role,
            "active": True,
            "assigned_by": assigned_by
        })
        .execute()
    )

    if not response.data:
        raise ClinicianAssignmentError(
        "Failed to assign clinician"
    )

    return response.data[0]


# ---- Get My Patients for Clinician ----
def get_my_patients(clinician_id: str):
    assignments = (
        supabase
        .table("clinicians_patients")
        .select("patient_id")
        .eq("clinician_id", clinician_id)
        .eq("active", True)
        .execute()
        .data
    )

    patient_ids = [a["patient_id"] for a in assignments]

    if not patient_ids:
        return []

    return (
        supabase
        .table("patients")
        .select("*")
        .in_("id", patient_ids)
        .execute()
        .data
    )


# ---- Get Patient Profile ----
def get_patient_profile(patient_id: str) -> Dict[str, Any]:
    response = (
        supabase
        .table("patients")
        .select("*")
        .eq("id", patient_id)
        .execute()
    )

    if not response.data:
        raise PatientNotFoundError(
        f"Patient {patient_id} not found"
    )

    patient = response.data[0]

    return {
        "id": patient.get("id"),
        "full_name": f"{patient.get('first_name','')} {patient.get('last_name','')}",
        "first_name": patient.get("first_name"),
        "last_name": patient.get("last_name"),
        "blood_group": patient.get("blood_group"),
        "gender": patient.get("gender"),
        "date_of_birth": patient.get("date_of_birth"),
        "phone": patient.get("phone"),
        "profile_image_url": patient.get("profile_image_url"),
        "emergency_contact": {
            "name": patient.get("emergency_contact_name"),
            "phone": patient.get("emergency_contact_phone")
        }
    }


# ---- Update Patient Info ----
def update_patient_info(patient_id: str, payload: dict):
    response = (
        supabase
        .table("patients")
        .update(payload)
        .eq("id", patient_id)
        .execute()
    )

    if not response.data:
        raise PatientUpdateError(
        "Failed to update patient"
    )

    return response.data[0]


# ---- Update Patient Profile Image ----
def update_profile_image(patient_id: str, image_url: str) -> Dict[str, Any]:
    response = (
        supabase_admin
        .table("patients")
        .update({"profile_image_url": image_url})
        .eq("id", patient_id)
        .execute()
    )

    if not response.data:
        raise PatientUpdateError(
        "Failed to update profile image"
    )   


    return response.data[0]


# ----- Get Patient Medical ID -----
def get_patient_medical_id(patient_id: str) -> str:

    response = (
        supabase_admin
        .table("patients")
        .select("medical_id")
        .eq("id", patient_id)
        .execute()
    )

    if not response.data or not isinstance(response.data, list) or len(response.data) == 0:
        raise ValueError("Patient not found")

    return str(response.data[0]["medical_id"])