import logging
from datetime import datetime, timezone
from typing import Any, cast
from app.core.supabase_admin import supabase_admin
from app.core.events.dispatcher import dispatch_event
from app.core.events.locking import (
    acquire_event_lock,
    recover_stuck_events,
    requeue_failed_events,
)
from app.core.events.state import (
    mark_processed,
    mark_failed,
)
from app.core.events.constants import BATCH_SIZE
from app.core.operational_event_policy import normalize_event_error_code


logger = logging.getLogger(__name__)


# ----- MAIN EVENT PROCESSOR -----
def process_pending_events():

    logger.info("Starting event processor")

    # Recover abandoned work
    recover_stuck_events()

    # Requeue eligible failed events
    requeue_failed_events()

    while True:

        events = cast(
            list[dict[str, Any]],
            (
                supabase_admin
                .table("events")
                .select("*")
                .in_("status", ["pending", "failed"])
                .order("created_at")
                .limit(BATCH_SIZE)
                .execute()
            ).data
            or []
        )

        if not events:
            logger.info("No pending events remaining.")
            break

        logger.info(
            "Processing batch of %s event(s)",
            len(events)
        )

        processed_this_batch = 0

        now = datetime.now(timezone.utc).isoformat()

        for event in events:

            event_id = event["id"]

            # Skip events waiting for retry
            next_retry_at = event.get("next_retry_at")
            if next_retry_at:
                retry_time = datetime.fromisoformat(
                    next_retry_at.replace("Z", "+00:00")
                )

                if retry_time > datetime.now(timezone.utc):
                    continue

            # Skip permanently exhausted retries
            if event.get("retry_count", 0) >= event.get("max_retries", 3):
                logger.warning(
                    "Operational event reached max retries"
                )
                continue

            # Acquire processing lock
            if not acquire_event_lock(event_id):
                continue

            logger.info(
                "Processing operational event"
            )

            try:

                dispatch_event(event)

                mark_processed(event_id)

                processed_this_batch += 1

            except Exception as e:

                logger.error(
                    "Operational event handler failed (%s)",
                    normalize_event_error_code(e),
                )

                mark_failed(
                    event_id,
                    reason=normalize_event_error_code(e),
                )

        # Safety guard against infinite loops
        if processed_this_batch == 0:
            logger.warning(
                "No events processed in this batch. Stopping processor."
            )
            break

    logger.info("Event processor finished.")


# ----- OPTIONAL DEBUG QUERY HELPERS -----
def fetch_pending_events():
    """
    Debug helper (not used in main loop anymore)
    """
    return (
        supabase_admin
        .table("events")
        .select("*")
        .eq("status", "pending")
        .limit(BATCH_SIZE)
        .execute()
        .data
    )


def should_process(event: dict[str, Any]) -> bool:
    """
    Phase 3 scheduling gate (optional reuse elsewhere)
    """
    now = datetime.now(timezone.utc).isoformat()

    next_retry_at = event.get("next_retry_at")

    if not next_retry_at:
        return True

    return next_retry_at <= now
