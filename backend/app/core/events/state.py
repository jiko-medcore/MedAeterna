from datetime import datetime, timezone
from app.core.supabase_admin import supabase_admin
from app.core.events.schemas import EventStatus
from app.core.events.constants import MAX_RETRIES
from app.core.events.backoff import compute_next_retry_at
from app.core.events.dead_letter import move_to_dead_letter


# -----------------------------
# MARK EVENT AS PROCESSED
# ----------------------------
def mark_processed(event_id: str):

    supabase_admin.table("events").update({
        "status": EventStatus.PROCESSED,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "next_retry_at": None,
        "last_error": None
    }).eq("id", event_id).execute()


# -----------------------------
# MARK EVENT AS FAILED (PHASE 3)
# -----------------------------
def mark_failed(event_id: str, reason: str):

    event = (
        supabase_admin
        .table("events")
        .select("id, event_type, aggregate_type, aggregate_id, payload, retry_count")
        .eq("id", event_id)
        .single()
        .execute()
    ).data

    retry_count = int(event.get("retry_count", 0)) + 1

    # DEAD LETTER TRANSITION
    if retry_count >= MAX_RETRIES:

        # mark dead in main table
        supabase_admin.table("events").update({
            "retry_count": retry_count,
            "status": EventStatus.DEAD,
            "last_error": reason,
            "next_retry_at": None,
            "processed_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", event_id).execute()

        # move to DLQ
        move_to_dead_letter(
                    {
            **event,
            "retry_count": retry_count
        }, 
            reason
            )

        return

    # RETRY SCHEDULING (BACKOFF)
    next_retry_at = compute_next_retry_at(retry_count)

    supabase_admin.table("events").update({
        "retry_count": retry_count,
        "status": EventStatus.FAILED,
        "last_error": reason,
        "next_retry_at": next_retry_at,
        "processed_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", event_id).execute()