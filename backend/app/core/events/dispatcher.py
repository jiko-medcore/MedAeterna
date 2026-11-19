from app.core.events.registry import EVENT_HANDLERS
from app.core.events.exceptions import (
    EventProcessingError,
    EventHandlerNotFoundError
)
import logging


logger = logging.getLogger(__name__)

#  ----- Event Dispatcher -----
def dispatch_event(event: dict):

    event_type = event.get("event_type")

    if not event_type:
        raise EventProcessingError(
            "Missing event_type"
        )
    
    handler = EVENT_HANDLERS.get(event_type)

    if not handler:
        raise EventHandlerNotFoundError(
            f"No handler registered for "
            f"event type '{event_type}'"
        )

    logger.info("Dispatching registered operational event handler")

    handler(event)
