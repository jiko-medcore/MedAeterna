from app.core.supabase_admin import supabase_admin
import logging


logger = logging.getLogger(__name__)


# ----- Event Based Emitter infrastructure -----
def emit_event(
    aggregate_type: str,
    aggregate_id: str,
    event_type: str,
    payload: dict | None = None
):
    
    result= (
        supabase_admin
        .table("events")
        .insert({
            "aggregate_type": aggregate_type,
            "aggregate_id": aggregate_id,
            "event_type": event_type,
            "payload": payload or {}
        })
        .execute()
    )

    logger.info("Operational event emitted")

    return result
