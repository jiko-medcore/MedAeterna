from app.core.events.emitter import emit_event
from app.core.events.schemas import EventTypes
from app.core.events.registry import register
from app.modules.patients.onboarding import send_onboarding_email
from app.core.supabase_admin import supabase_admin
from app.core.events.service import EventService
import logging


logger= logging.getLogger(__name__)


# ----- Patient Create Hanlder ----- 
@register(EventTypes.PATIENT_CREATED)
def handle_patient_created(event):
    logger.info("Patient event handler started")

    emit_event(
        aggregate_type="patient",
        aggregate_id=event["aggregate_id"],
        event_type=EventTypes.ONBOARDING_EMAIL_REQUESTED,
        payload=event["payload"]
    )

    logger.info("Patient onboarding notification was queued")
    

# ----- Onboarding Email Request Handler -----
@register(EventTypes.ONBOARDING_EMAIL_REQUESTED)
def handle_onboarding_email_requested(event):

    patient_id = event["aggregate_id"]

    try:
        send_onboarding_email(patient_id)

        EventService.onboarding_email_sent(patient_id)

    except Exception as e:

        EventService.onboarding_email_failed(
            patient_id,
            str(e)
        )

        raise


# ----- Onboarding Email Sent Handler -----
@register(EventTypes.ONBOARDING_EMAIL_SENT)
def handle_onboarding_email_sent(event):

    logger.info(
        "Patient onboarding notification completed"
    )
