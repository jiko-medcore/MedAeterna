from app.core.events.registry import register
from app.core.events.schemas import EventTypes
from app.core.events.emitter import emit_event
from app.modules.organizations.onboarding import (
    send_organization_onboarding_email,
    )
import logging

logger= logging.getLogger(__name__)

# --------------------------------------------------------
#           Organization Created Handler
# --------------------------------------------------------
@register(EventTypes.ORGANIZATION_CREATED)
def handle_organization_created(event):

    organization_id = event["aggregate_id"]

    emit_event(
        aggregate_type="organization",
        aggregate_id=organization_id,
        event_type=EventTypes.ORGANIZATION_ONBOARDING_REQUESTED,
        payload=event.get("payload", {})
    )


# ------------------------------------------------------------
#           Organization Onboarding Handler
# ------------------------------------------------------------
@register(EventTypes.ORGANIZATION_ONBOARDING_REQUESTED)
def handle_organization_onboarding(event):

    organization_id = event["aggregate_id"]

    try:

        send_organization_onboarding_email(
            organization_id,
            event.get("payload", {})
        )

        emit_event(
            aggregate_type="organization",
            aggregate_id=organization_id,
            event_type=EventTypes.ORGANIZATION_ONBOARDING_COMPLETED
        )

    except Exception as exc:

        emit_event(
            aggregate_type="organization",
            aggregate_id=organization_id,
            event_type=EventTypes.ORGANIZATION_ONBOARDING_FAILED,
            payload={
                "error": str(exc)
            }
        )

        raise


# ----------------------------------------------------
#           Onboarding Complete Handler
# -----------------------------------------------------
@register(EventTypes.ORGANIZATION_ONBOARDING_COMPLETED)
def handle_organization_onboarding_completed(event):
    logger.info("Organization onboarding completed")
