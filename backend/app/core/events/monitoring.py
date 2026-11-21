"""Internal operational-event data access.

These helpers use explicit safe metadata projections. Payloads, aggregate
identifiers and raw failure text are not returned to callers.
"""

from fastapi import HTTPException
from app.core.supabase_admin import supabase_admin

EVENT_METADATA_SELECT = (
    "id, aggregate_type, event_type, status, created_at, processed_at, retry_count"
)
DEAD_LETTER_METADATA_SELECT = (
    "id, aggregate_type, event_type, retry_count, failed_at, replayed, replayed_at"
)


# -----------------------------
# GET EVENTS (FILTERABLE)
# -----------------------------
def get_events(status: str | None = None, limit: int = 100):

    query = (
        supabase_admin
        .table("events")
        .select(EVENT_METADATA_SELECT)
        .order("created_at", desc=True)
        .limit(limit)
    )

    if status:
        query = query.eq("status", status)

    return query.execute().data


# -----------------------------
# GET EVENT BY ID
# -----------------------------
def get_event(event_id: str):

    event= (
        supabase_admin
        .table("events")
        .select(EVENT_METADATA_SELECT)
        .eq("id", event_id)
        .single()
        .execute()
        .data
    )

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    return event


# -----------------------------
# EVENT STATS (CORE HEALTH METRICS)
# -----------------------------
def get_event_stats():

    events = (
        supabase_admin
        .table("events")
        .select("status")
        .execute()
        .data
    )

    total = len(events)

    stats = {
        "total": total,
        "pending": 0,
        "processing": 0,
        "processed": 0,
        "failed": 0,
        "dead": 0,
    }

    for e in events:
        status = e.get("status")
        if status in stats:
            stats[status] += 1

    stats["success_rate"] = (
        stats["processed"] / total * 100
        if total > 0 else 0
    )

    return stats


# -----------------------------
# FAILED EVENTS
# -----------------------------
def get_failed_events(limit: int = 100):

    return (
        supabase_admin
        .table("events")
        .select(EVENT_METADATA_SELECT)
        .eq("status", "failed")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )


# -----------------------------
# DEAD LETTER EVENTS
# -----------------------------
def get_dead_letter_events(limit: int = 100):

    return (
        supabase_admin
        .table("events_dead_letter")
        .select(DEAD_LETTER_METADATA_SELECT)
        .order("failed_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )


# ------------------------
# GET DEAD LETTER EVENT ID
# ------------------------
def get_dead_letter_event(
    dead_event_id: str
):

    event = (
        supabase_admin
        .table("events_dead_letter")
        .select(DEAD_LETTER_METADATA_SELECT)
        .eq("id", dead_event_id)
        .single()
        .execute()
        .data
    )

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Dead letter event not found"
        )

    return event