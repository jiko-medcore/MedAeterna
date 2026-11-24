"""Controlled dead-letter replay.

The admin route is responsible for role/purpose/reason authorization and for
writing attributable attempt and final-outcome audit records. This module only
performs the privileged state transition.
"""

from datetime import datetime, timezone

from app.core.supabase_admin import supabase_admin

# Internal replay needs the original payload, but never raw failure text.
DEAD_LETTER_REPLAY_SELECT = (
    "id, original_event_id, aggregate_type, aggregate_id, event_type, "
    "payload, retry_count, replayed"
)


def replay_dead_event(dead_event_id: str, actor_id: str):
    dead_event = (
        supabase_admin.table("events_dead_letter")
        .select(DEAD_LETTER_REPLAY_SELECT)
        .eq("id", dead_event_id)
        .limit(1)
        .execute()
    ).data

    if not dead_event:
        raise ValueError("Dead letter event not found")
    item = dead_event[0]
    if item.get("replayed"):
        raise ValueError("Event already replayed")

    # Compare-and-set: only one caller can claim an unreplayed dead-letter row.
    claimed = (
        supabase_admin.table("events_dead_letter")
        .update(
            {
                "replayed": True,
                "replayed_at": datetime.now(timezone.utc).isoformat(),
                "replayed_by": actor_id,
            }
        )
        .eq("id", dead_event_id)
        .eq("replayed", False)
        .select("id")
        .execute()
    ).data
    if not claimed:
        raise ValueError("Event already replayed or unavailable for replay")

    try:
        new_event = (
            supabase_admin.table("events")
            .insert(
                {
                    "aggregate_type": item.get("aggregate_type"),
                    "aggregate_id": item.get("aggregate_id"),
                    "event_type": item.get("event_type"),
                    "payload": item.get("payload"),
                    "status": "pending",
                    "retry_count": 0,
                    "next_retry_at": None,
                }
            )
            .execute()
        ).data[0]
    except Exception:
        # Compensating action if queue insertion fails after the CAS claim.
        # Single-transaction atomicity still requires a reviewed database
        # function and remains separate remediation work.
        (
            supabase_admin.table("events_dead_letter")
            .update({"replayed": False, "replayed_at": None, "replayed_by": None})
            .eq("id", dead_event_id)
            .eq("replayed", True)
            .execute()
        )
        raise

    return {
        "message": "Event replayed successfully",
        "new_event_id": new_event["id"],
    }
