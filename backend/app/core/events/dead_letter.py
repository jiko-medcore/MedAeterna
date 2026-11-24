from datetime import datetime, timezone

from app.core.audit.actions import AuditActions
from app.core.audit.service import log_audit_event
from app.core.supabase_admin import supabase_admin


# -----------------------------
# MOVE EVENT TO DLQ
# -----------------------------
def move_to_dead_letter(event: dict, reason: str):
    event_id = event.get("id")
    retry_count = event.get("retry_count", 0)
    (
        supabase_admin.table("events_dead_letter")
        .insert(
            {
                "original_event_id": event_id,
                "aggregate_type": event.get("aggregate_type"),
                "aggregate_id": event.get("aggregate_id"),
                "event_type": event.get("event_type"),
                "payload": event.get("payload"),
                "retry_count": retry_count,
                "failure_reason": reason,
                "failed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .execute()
    )

    try:
        log_audit_event(
            actor_id=None,
            actor_type="system",
            action=AuditActions.EVENT_DEAD_LETTERED,
            resource_type="event",
            resource_id=str(event_id) if event_id is not None else "",
            metadata={"reason": reason, "retry_count": retry_count},
        )
    except Exception:
        # Do not emit sensitive details to logs; audit failures are surfaced by callers/monitors.
        pass
