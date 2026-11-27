import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.core.clinical_authorization import (
    CLINICAL_RECORD,
    authorize_clinical_access,
    authorize_patient_list_access,
    authorize_patient_profile_access,
)
from app.core.patient_avatar_access import (
    create_signed_patient_avatar_url,
    is_patient_avatar_object_path,
)
from app.core.security import authorize_patient_access, get_current_user, require_permission
from app.core.storage_access_inventory import PATIENT_AVATARS_BUCKET
from app.core.storage_upload_validation import (
    StorageUploadValidationError,
    validate_image_upload,
)
from app.core.supabase_admin import supabase_admin
from app.modules.patients.schemas import Patient, PatientUpdate
from app.modules.patients.service import (
    assign_clinician_to_patient,
    build_patient_timeline,
    get_my_patients,
    get_or_create_patient,
    get_patient_medical_id,
    get_patient_profile,
    get_patient_summary,
    get_patient_with_records,
    PATIENT_PROFILE_UPDATE_FIELDS,
    update_patient_info,
    update_profile_image_path,
)
from app.shared.tasks.event_tasks import process_events_task
from app.shared.utils.fhir import build_patient_bundle
from app.shared.utils.qr import generate_qr

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get("/medical-id")
def get_medical_id(current_user: dict = Depends(get_current_user)):
    context = authorize_patient_profile_access(
        current_user,
        action="read",
        patient_id=str(current_user.get("id") or ""),
    )
    return {
        "medical_id": get_patient_medical_id(
            str(current_user["id"]), authorized_context=context
        )
    }


@router.get("/me", response_model=Patient)
def get_create_patient(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    if not current_user.get("is_patient"):
        raise HTTPException(status_code=403, detail="Only patients can access this endpoint")

    result = get_or_create_patient(current_user["id"], current_user.get("email") or "")
    if result is None:
        raise HTTPException(status_code=404, detail="Patient not found or could not be created")

    patient = result["patient"]
    if result.get("created"):
        background_tasks.add_task(process_events_task)
    return patient


@router.get("/profile/me")
def my_profile(current_user: dict = Depends(get_current_user)):
    context = authorize_patient_profile_access(
        current_user,
        action="read",
        patient_id=str(current_user.get("id") or ""),
    )
    return get_patient_profile(
        str(current_user["id"]), authorized_context=context
    )


@router.get("/mine")
def my_patients(current_user: dict = Depends(get_current_user)):
    # Use deterministic role categories and trusted care-team relationships.
    # Legacy clinician flags and client-supplied organization context are not
    # sufficient to enumerate patient records.
    return get_my_patients(
        authorized_context=authorize_patient_list_access(current_user)
    )


@router.put("/profile/me")
def update_my_profile(
    payload: PatientUpdate,
    current_user: dict = Depends(get_current_user),
):
    update_data = payload.model_dump(exclude_unset=True)
    context = authorize_patient_profile_access(
        current_user,
        action="update",
        patient_id=str(current_user.get("id") or ""),
        permitted_fields=bool(update_data) and set(update_data).issubset(
            PATIENT_PROFILE_UPDATE_FIELDS
        ),
    )
    return update_patient_info(
        str(current_user["id"]),
        update_data,
        authorized_context=context,
    )


@router.get("/{patient_id}/fhir")
def patient_fhir(
    patient_id: str,
    current_user: dict = Depends(get_current_user),
):
    context = authorize_clinical_access(
        current_user,
        resource=CLINICAL_RECORD,
        action="read",
        patient_id=str(patient_id),
    )
    patient, records = get_patient_with_records(
        str(patient_id),
        authorized_context=context,
    )
    return build_patient_bundle(patient, records)


@router.get("/{patient_id}/qr")
def patient_qr(
    patient_id: str,
    current_user: dict = Depends(get_current_user),
):
    authorize_patient_access(current_user, str(patient_id))
    # The QR payload contains only the authorized patient identifier; fetching
    # patient or clinical rows here would be unnecessary overexposure.
    return StreamingResponse(generate_qr(str(patient_id)), media_type="image/png")


@router.get("/{patient_id}/summary", tags=["Patients"])
def patient_summary(
    patient_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    # Derive organization scope from the target patient and fail closed.
    context = authorize_clinical_access(
        current_user,
        resource=CLINICAL_RECORD,
        action="read",
        patient_id=str(patient_id),
    )
    return get_patient_summary(str(patient_id), authorized_context=context)


@router.get("/{patient_id}/timeline")
def get_patient_timeline(
    patient_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    context = authorize_clinical_access(
        current_user,
        resource=CLINICAL_RECORD,
        action="read",
        patient_id=str(patient_id),
    )
    return build_patient_timeline(patient_id, authorized_context=context)


@router.post("/{patient_id}/assign")
def assign_patient(
    patient_id: str,
    clinician_id: str,
    role: str = "primary",
    current_user: dict = Depends(require_permission("assign_patient")),
):
    # Permission check is organization-scoped by the dependency contract; also
    # ensure the caller can act for this specific patient/org context.
    authorize_patient_access(current_user, str(patient_id), organization_id=current_user.get("authorized_organization_id"))
    return assign_clinician_to_patient(
        clinician_id=clinician_id,
        patient_id=patient_id,
        role=role,
        assigned_by=current_user["id"],
    )


@router.post("/profile/upload-avatar")
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    context = authorize_patient_profile_access(
        current_user,
        action="update",
        patient_id=str(current_user.get("id") or ""),
        permitted_fields=True,
    )

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
    if not is_patient_avatar_object_path(file_path, current_user["id"]):
        raise HTTPException(status_code=400, detail="Invalid avatar object path")

    bucket = None
    uploaded = False
    try:
        bucket = supabase_admin.storage.from_(PATIENT_AVATARS_BUCKET)
        bucket.upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": file.content_type, "upsert": "true"},
        )
        uploaded = True

        # The signed URL is returned to the caller only. The database receives
        # the stable object path, never this ephemeral URL.
        signed_url = create_signed_patient_avatar_url(
            patient_id=str(current_user["id"]),
            object_path=file_path,
        )
        update_profile_image_path(
            str(current_user["id"]),
            file_path,
            authorized_context=context,
        )
        return {
            "message": "Profile image uploaded successfully",
            "profile_image_url": signed_url,
        }
    except Exception:
        if uploaded and bucket is not None:
            try:
                bucket.remove([file_path])
            except Exception:
                # Do not log object paths, URLs, bytes, or exception details.
                logger.error("Patient avatar compensation removal failed")
        logger.error("Patient avatar upload failed")
        raise HTTPException(status_code=500, detail="Avatar upload failed")
