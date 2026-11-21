from app.core.events.emitter import emit_event
from app.core.events.schemas import (
    EventTypes,
    EventStatus
)
from app.core.supabase_admin import supabase_admin


# ----- Patient Create Event Service Layer ----- 
class EventService:
    @staticmethod
    def patient_created(
        patient_id: str,
        email: str | None
    ):
        emit_event(
            aggregate_type="patient",
            aggregate_id=patient_id,
            event_type=EventTypes.PATIENT_CREATED,
            payload={
                "email": email
            }
        )

    @staticmethod
    def retry_event(
        event_id: str
    ):

        return (
            supabase_admin
            .table("events")
            .update({
                "status": EventStatus.PENDING,
                "failure_reason": None,
                "locked_at": None,
                "last_attempt_at": None
            })
            .eq("id", event_id)
            .eq("status", EventStatus.FAILED)
            .lt("retry_count", 3)
            .execute()
        )

    # ----- Onboarding Email Request Event Service Layer -----
    @staticmethod
    def onboarding_email_requested(
        patient_id: str,
        email: str | None
    ):

        emit_event(
            aggregate_type="patient",
            aggregate_id=patient_id,
            event_type=EventTypes.ONBOARDING_EMAIL_REQUESTED,
            payload={
                "email": email
            }
        )


    # ----- Onboarding Email Sent Event Service Layer -----
    @staticmethod
    def onboarding_email_sent(
        patient_id: str
    ):

        emit_event(
            aggregate_type="patient",
            aggregate_id=patient_id,
            event_type=EventTypes.ONBOARDING_EMAIL_SENT
        )

    #  ----- Onboarding Email Failed Event -----
    @staticmethod
    def onboarding_email_failed(
        patient_id: str,
        reason: str
    ):

        emit_event(
            aggregate_type="patient",
            aggregate_id=patient_id,
            event_type=EventTypes.ONBOARDING_EMAIL_FAILED,
            payload={
                "reason": reason
            }
        )