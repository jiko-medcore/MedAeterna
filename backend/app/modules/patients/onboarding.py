from datetime import datetime, timezone
from app.core.supabase_admin import supabase_admin
from app.shared.email.email_service import send_email
from app.shared.services.template_service import render_template
from app.shared.schemas.email_service import EmailService
from pydantic import ValidationError
from app.modules.patients.exceptions import EmailDeliveryError
from app.core.audit.service import log_audit_event
from app.core.audit.actions import AuditActions
import logging

logger = logging.getLogger(__name__)


# ----- Onboarding Patient Email Serivice -----
def send_onboarding_email(patient_id: str):

    logger.info("ONBOARDING_EMAIL_STARTED")

    try:
        result = (
            supabase_admin
            .table("patients")
            .select("*")
            .eq("id", patient_id)
            .maybe_single()
            .execute()
        )
        patient = getattr(result, "data", None) if result is not None else None
    except Exception:
        logger.warning("Patient lookup failed during onboarding")
        return

    if not patient:
        logger.warning("Patient not found or invalid data during onboarding")
        return {"status": "not_found"}
    
    
    if patient.get("onboarding_email_sent") and patient.get("onboarding_completed"):
        return

    email = patient.get("email")

    if not email:
        return {"status": "missing_email"}

    try:
        #  verify start
        logger.info("RENDER TEMPLATE START")

        html = render_template(
            "welcome_patient.html",
            {
                "first_name": patient.get("first_name"),
                "medical_id": patient.get("medical_id")
            }
        )

        # verify end
        logger.info("RENDER TEMPLATE SUCCESS")

        try:
            email_service = EmailService(
            to=email,
            subject="Welcome to MedCore",
            html=html
        )
        except (ValidationError, TypeError) as ve:
            logger.warning("Invalid patient email in onboarding record")
            (
                supabase_admin
                .table("patients")
                .update({
                    "onboarding_last_error": "invalid_email",
                    "onboarding_failure_reason": "invalid_email",
                    "onboarding_retry_count": int(patient.get("onboarding_retry_count") or 0) + 1,
                    "onboarding_status": "processing",
                    "onboarding_last_attempt_at": datetime.now(timezone.utc).isoformat()
                })
                .eq("id", patient_id)
                .execute()
            )
            return {"status": "invalid_email"}
        
        # send the prepared EmailService instance without logging recipient or provider response
        response = send_email(email_service)

        # audit write carries attribution; no raw response or patient row is logged
        log_audit_event(
            actor_id=patient_id,
            actor_type="patient",
            action=AuditActions.ONBOARDING_EMAIL_SENT,
            resource_type="patient",
            resource_id=patient_id
        )

        if not response:
            raise EmailDeliveryError("Email send failed")
        
        now = datetime.now(timezone.utc).isoformat()

        (
            supabase_admin
            .table("patients")
            .update({
                "onboarding_email_sent": True,
                "onboarding_email_sent_at": now,
                "onboarding_retry_count": 0,
                "onboarding_last_error": None,
                "onboarding_status": "completed",
                "onboarding_completed": True,
                "onboarding_completed_at": now
            })
            .eq("id", patient_id)
            .execute()
        )

    except Exception:
        logger.exception("Failed to send onboarding email")

        (
            supabase_admin
            .table("patients")
            .update({
                "onboarding_last_error": "email_delivery_failed",
                "onboarding_failure_reason": "email_delivery_failed",
                "onboarding_retry_count": int(patient.get("onboarding_retry_count") or 0) + 1,
                "onboarding_status": "failed",
                "onboarding_last_attempt_at": datetime.now(timezone.utc).isoformat()
            })
            .eq("id", patient_id)
            .execute()
        )

        raise

