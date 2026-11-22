from datetime import datetime, timezone

from fastapi import HTTPException

from app.core.supabase_admin import supabase_admin


def _aware(value: datetime | None, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise HTTPException(status_code=400, detail=f"{field} must include a timezone")
    return value


# ----- Grant Consent Service for Practitioners -----
def grant_consent(
    patient_id: str,
    payload,
    *,
    actor_user_id: str,
):
    """Create an active consent record through the trusted backend path.

    SPEC-05 authority and finite-expiry requirements are enforced here and by
    database constraints. Purpose codes, recipient-kind storage and resource
    scope storage remain undecided and are deliberately not inferred.
    """
    granted_at = datetime.now(timezone.utc)
    effective_from = _aware(payload.effective_from, "effective_from") if payload.effective_from else granted_at
    expires_at = _aware(payload.expires_at, "expires_at")
    if expires_at <= granted_at or expires_at <= effective_from:
        raise HTTPException(status_code=400, detail="expires_at must follow the grant and effective time")
    if payload.emergency_access is not False:
        raise HTTPException(status_code=400, detail="emergency consent cannot authorize access")

    response = (
        supabase_admin
        .table("consent_records")
        .insert({
            "patient_id": patient_id,
            "organization_id": payload.organization_id,
            "practitioner_id": payload.practitioner_id,
            "consent_type": payload.consent_type,
            "access_level": payload.access_level,
            "purpose_of_use": payload.purpose_of_use,
            "legal_basis": payload.legal_basis,
            "emergency_access": False,
            "effective_from": effective_from.isoformat(),
            "expires_at": expires_at.isoformat(),
            "granted_by": str(actor_user_id),
            "granted_at": granted_at.isoformat(),
            "metadata": payload.metadata,
            "status": "active",
        })
        .execute()
    )

    return response.data[0]


# ----- Revoke Consent Service -----
def revoke_consent(
    patient_id: str,
    payload,
    *,
    actor_user_id: str,
):
    existing = (
        supabase_admin
        .table("consent_records")
        .select("*")
        .eq("id", payload.consent_id)
        .eq("patient_id", patient_id)
        .limit(1)
        .execute()
    )

    if not existing.data:
        raise HTTPException(
            status_code=404,
            detail="Consent not found"
        )

    revoked_at = datetime.now(timezone.utc)
    response = (
        supabase_admin
        .table("consent_records")
        .update({
            "status": "revoked",
            "revoked_reason": payload.revoked_reason,
            "revoked_by": str(actor_user_id),
            "revoked_at": revoked_at.isoformat(),
        })
        .eq("id", payload.consent_id)
        .eq("patient_id", patient_id)
        .execute()
    )

    return response.data[0]


# ---- Get List of Existing Consent Service ----
def get_patient_consents(
    patient_id: str
):

    response = (
        supabase_admin
        .table("consent_records")
        .select("""
            *,
            organizations (
                id,
                name
            ),
            practitioners (
                id,
                first_name,
                last_name,
                photo
            )
        """)
        .eq("patient_id", patient_id)
        .order("created_at", desc=True)
        .execute()
    )

    return response.data
