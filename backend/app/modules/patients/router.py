from fastapi import (
    APIRouter, 
    Depends, 
    HTTPException,
    UploadFile,
    File,
    BackgroundTasks
)
from fastapi.responses import StreamingResponse
from app.core.security import (
    get_current_user, 
    require_patient_access,
    require_permission
    )
from app.core.storage_access_inventory import PATIENT_AVATARS_BUCKET
from app.core.storage_upload_validation import (
    StorageUploadValidationError,
    validate_image_upload,
)
from app.core.supabase_admin import supabase_admin
from app.core.supabase_client import supabase
from app.modules.patients.service import (
    build_patient_timeline,
    get_or_create_patient,
    get_patient_with_records,
    assign_clinician_to_patient,
    get_patient_summary,
    get_my_patients,
    get_patient_profile,
    update_patient_info,
    update_profile_image,
    get_patient_medical_id
    )
from app.modules.patients.schemas import (
    Patient,
    PatientUpdate
)
from app.shared.utils.fhir import build_patient_bundle
from app.shared.utils.qr import generate_qr
from app.shared.tasks.event_tasks import (
    process_events_task
)
from uuid import UUID
import logging


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/patients", tags=["Patients"])


# ---- Add Medical ID Endpoint -----
@router.get("/medical-id")
def get_medical_id(
    current_user=Depends(get_current_user)
):

    return {
        "medical_id": get_patient_medical_id(
            current_user["id"]
        )
    }


# ----- Create Patient Record -----
@router.get("/me", response_model=Patient)
def get_create_patient(
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user)
    ):
    
    # Only patients can access this endpoint
    if not current_user["is_patient"]:
        raise HTTPException(403, "Only patients can access this endpoint")
    
    result = get_or_create_patient(current_user["id"], current_user["email"]) 

    # get_or_create_patient may return None, a single patient, or (patient, created)
    if result is None:
        raise HTTPException(status_code=404, detail="Patient not found or could not be created")

    patient = result["patient"]
    created = result["created"]

    if created:
        background_tasks.add_task(process_events_task)

    return patient


# ---- Get My Patient Profile -----
@router.get("/profile/me")
def my_profile(current_user=Depends(get_current_user)):

    if not current_user["is_patient"]:
        raise HTTPException(403, "Only patients allowed")

    return get_patient_profile(current_user["id"])




# ----- Get My Patients (for Clinicians) -----
@router.get("/mine")
def my_patients(current_user=Depends(get_current_user)):
    if current_user["role"] != "clinician":
        raise HTTPException(status_code=403, detail="Only clinicians allowed")

    return get_my_patients(current_user["id"])


# --- Update My Patient Profile -----
@router.put("/profile/me")
def update_my_profile(
    payload: PatientUpdate,
    current_user=Depends(get_current_user)
):
    if not current_user["is_patient"]:
        raise HTTPException(403, "Only patients allowed")

    return update_patient_info(current_user["id"], payload.model_dump(exclude_unset=True))



# ----- Get Patient FHIR Bundle -----
@router.get("/{patient_id}/fhir")
def patient_fhir(
    patient_id: str,
    current_user=Depends(get_current_user)
):
    # Patient level access control
    require_patient_access(patient_id, current_user)

    # Get patient and records
    patient, records = get_patient_with_records(patient_id)

    return build_patient_bundle(patient, records)


# ----- Get Patient QR Code -----
@router.get("/{patient_id}/qr")
def patient_qr(
    patient_id: str,
    current_user=Depends(get_current_user)
):
    # Patient level access control
    require_patient_access(patient_id, current_user)

    # Validate patient exists and access is allowed
    get_patient_with_records(patient_id)

    return StreamingResponse(
        generate_qr(patient_id),
        media_type="image/png"
    )


# ----- Get Patient Summary -----
@router.get("/{patient_id}/summary", tags=["Patients"])
def patient_summary(
    patient_id: UUID,
    current_user=Depends(require_permission("read_patient_summary"))
):
    # Patient level access control
    require_patient_access(str(patient_id), current_user)
    return get_patient_summary(str(patient_id))


# ----- Get Patient Timeline -----
@router.get("/{patient_id}/timeline")
def get_patient_timeline(
    patient_id: UUID,
    current_user=Depends(require_permission("view_patient"))
):
    #  Patient level access control
    require_patient_access(str(patient_id), current_user)
    return build_patient_timeline(patient_id)


# ---- Assign Clinician to Patient -----
@router.post("/{patient_id}/assign")
def assign_patient(
    patient_id: str,
    clinician_id: str,
    role: str = "primary",
    current_user=Depends(require_permission("assign_patient"))
):
    return assign_clinician_to_patient(
        clinician_id=clinician_id,
        patient_id=patient_id,
        role=role,
        assigned_by=current_user["id"]
    )


# ---- Upload Profile Picture -----
@router.post("/profile/upload-avatar")
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user)
):
    if not current_user["is_patient"]:
        raise HTTPException(403, "Only patients allowed")

    file_bytes = await file.read()

    try:
        extension = validate_image_upload(
            bucket=PATIENT_AVATARS_BUCKET,
            content_type=file.content_type,
            content=file_bytes,
        )
    except StorageUploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    file_path = f"{current_user['id']}/avatar.{extension}"

    try:
        bucket = supabase_admin.storage.from_(PATIENT_AVATARS_BUCKET)
        bucket.upload(
            path=file_path,
            file=file_bytes,
            file_options={
                "content-type": file.content_type,
                "upsert": "true",
            },
        )
        public_url = bucket.get_public_url(file_path)
        update_profile_image(current_user["id"], public_url)

        return {
            "message": "Profile image uploaded successfully",
            "profile_image_url": public_url
        }
    except Exception:
        logger.exception(
            "Avatar upload failed for patient %s",
            current_user["id"]
        )

        raise HTTPException(
            status_code=500,
            detail="Avatar upload failed"
        )