"""SPEC-09 operational-event visibility and retry policy reference model."""

from __future__ import annotations

from collections.abc import Iterable

from app.core.action_authorization import ActionDecision, evaluate_action
from app.core.role_catalogue import ORGANIZATION_ADMINISTRATOR, SYSTEM_ADMINISTRATOR


KNOWN_EVENT_TYPES = frozenset(
    {
        "patient.created",
        "onboarding.email_requested",
        "onboarding.email_sent",
        "onboarding.email_failed",
        "organization.created",
        "organization.onboarding.requested",
        "organization.onboarding.completed",
        "organization.onboarding.failed",
        "organization.profile.updated",
        "department.created",
        "department.updated",
        "department.deleted",
        "department.onboarding.requested",
        "department.onboarding.completed",
        "healtcare_service.created",
        "healtcare_service.updated",
        "healthcare_service.updated",
        "healthcare_service.activated",
        "healthcare_service.deactivated",
        "operating_hours.created",
        "operating_hours.updated",
        "operating_hours.deleted",
        "organization.branding.updated",
        "organization.logo.updated",
        "organization.logo.removed",
    }
)

ORGANIZATION_EVENT_AGGREGATES = {
    "organization": frozenset(
        {
            "organization.created",
            "organization.onboarding.requested",
            "organization.onboarding.completed",
            "organization.onboarding.failed",
            "organization.profile.updated",
            "organization.branding.updated",
            "organization.logo.updated",
            "organization.logo.removed",
        }
    ),
    "department": frozenset(
        {
            "department.created",
            "department.updated",
            "department.deleted",
            "department.onboarding.requested",
            "department.onboarding.completed",
        }
    ),
    "healthcare_service": frozenset(
        {
            "healtcare_service.created",
            "healthcare_service.updated",
            "healthcare_service.activated",
            "healthcare_service.deactivated",
        }
    ),
    "operating_hours": frozenset(
        {
            "operating_hours.created",
            "operating_hours.updated",
            "operating_hours.deleted",
        }
    ),
}

EVENT_STATUS_VALUES = frozenset(
    {"pending", "processing", "processed", "failed", "dead"}
)
PATIENT_EVENT_TYPES = frozenset(
    {
        "patient.created",
        "onboarding.email_requested",
        "onboarding.email_sent",
        "onboarding.email_failed",
    }
)
EVENT_METADATA_FIELDS = frozenset(
    {
        "event_reference",
        "event_type",
        "status",
        "created_at",
        "processed_at",
        "retry_count",
        "normalized_error_code",
    }
)
EVENT_SUMMARY_FIELDS = frozenset(
    {"total", "pending", "processing", "processed", "failed", "dead", "success_rate"}
)
PATIENT_EVENT_METADATA_FIELDS = frozenset(
    {
        "event_reference",
        "status",
        "created_at",
        "processed_at",
        "retry_count",
        "normalized_error_code",
    }
)
ORGANIZATION_EVENT_PURPOSE = "organization_operations"
SYSTEM_EVENT_PURPOSES = frozenset({"platform_health", "security_incident"})
SYSTEM_RETRY_PURPOSES = frozenset({"event_recovery", "security_incident"})
RETRYABLE_EVENT_STATUSES = frozenset({"failed", "dead"})
MAX_MANUAL_RETRY_COUNT = 3
NORMALIZED_ERROR_CODES = frozenset(
    {
        "DEPENDENCY_TIMEOUT",
        "DEPENDENCY_UNAVAILABLE",
        "EVENT_HANDLER_NOT_FOUND",
        "INVALID_EVENT",
        "PROCESSING_FAILED",
    }
)

# SPEC-09 requires a reviewed retry-safety decision per event type before a
# handler may be manually retried. Registration alone is not proof of
# idempotency. Keep this empty until each handler is reviewed and approved.
MANUAL_RETRY_SAFE_EVENT_TYPES: frozenset[str] = frozenset()


def is_manual_retry_safe(event_type: str, registered_event_types: Iterable[str]) -> bool:
    """Only return True for an allowlisted, currently registered handler."""
    return (
        isinstance(event_type, str)
        and event_type in MANUAL_RETRY_SAFE_EVENT_TYPES
        and event_type in set(registered_event_types)
    )


def normalize_event_error_code(error: BaseException) -> str:
    """Map an exception to a fixed code without preserving its message."""
    if not isinstance(error, BaseException):
        return "PROCESSING_FAILED"
    if isinstance(error, TimeoutError):
        return "DEPENDENCY_TIMEOUT"
    if isinstance(error, (ConnectionError, OSError)):
        return "DEPENDENCY_UNAVAILABLE"
    if type(error).__name__ == "EventHandlerNotFoundError":
        return "EVENT_HANDLER_NOT_FOUND"
    if isinstance(error, (ValueError, TypeError)):
        return "INVALID_EVENT"
    return "PROCESSING_FAILED"


def normalize_event_error_text(value: object) -> str | None:
    """Map stored failure text to a fixed code; never return the raw text."""
    if not isinstance(value, str) or not value.strip():
        return None
    folded = value.casefold()
    if "timeout" in folded or "timed out" in folded:
        return "DEPENDENCY_TIMEOUT"
    if "unavailable" in folded or "connection" in folded or "network" in folded:
        return "DEPENDENCY_UNAVAILABLE"
    if "handler not found" in folded or "not registered" in folded:
        return "EVENT_HANDLER_NOT_FOUND"
    if "invalid event" in folded or "validation" in folded:
        return "INVALID_EVENT"
    # Any other stored error is a generic processing failure, never raw text.
    return "PROCESSING_FAILED"


def _requested_field_set(requested_fields: Iterable[str]) -> set[str] | None:
    try:
        fields = set(requested_fields)
    except TypeError:
        return None
    if not fields or any(not isinstance(field, str) for field in fields):
        return None
    if not fields.issubset(EVENT_METADATA_FIELDS):
        return None
    return fields


def evaluate_event_visibility(
    *,
    actor_roles: Iterable[dict],
    event_type: str,
    aggregate_type: str,
    status: str,
    requested_fields: Iterable[str],
    purpose: str,
    organization_id: str | None = None,
    resolved_organization_id: str | None = None,
    event_payload_redacted: bool = False,
    patient_data_redacted: bool = False,
    event_visibility_approved: bool = False,
    audit_recorded: bool = False,
) -> ActionDecision:
    """Evaluate one sanitized event-metadata read using trusted scope evidence."""
    if (
        not isinstance(event_type, str)
        or not isinstance(aggregate_type, str)
        or not isinstance(status, str)
        or event_type not in KNOWN_EVENT_TYPES
        or status not in EVENT_STATUS_VALUES
    ):
        return ActionDecision("deny", "event type or state is not recognized")
    actor_role_list = tuple(actor_roles)

    conditions: set[str] = set()
    if event_payload_redacted:
        conditions.add("event_payload_redacted")
    if event_visibility_approved:
        conditions.add("event_visibility_approved")
    if audit_recorded:
        conditions.add("audit_recorded")

    categories = {role.get("category") for role in actor_role_list}
    if purpose == ORGANIZATION_EVENT_PURPOSE:
        if ORGANIZATION_ADMINISTRATOR not in categories:
            return ActionDecision("deny", "role has no organization event visibility")
        fields = _requested_field_set(requested_fields)
        if fields is None:
            return ActionDecision("deny", "event fields exceed the approved metadata projection")
        if event_type not in ORGANIZATION_EVENT_AGGREGATES.get(aggregate_type, frozenset()):
            return ActionDecision("deny", "event is not visible to organization administrators")
        if (
            not organization_id
            or not resolved_organization_id
            or str(organization_id) != str(resolved_organization_id)
        ):
            return ActionDecision("deny", "event is outside the verified organization scope")
        if purpose != ORGANIZATION_EVENT_PURPOSE:
            return ActionDecision("deny", "organization event purpose is not approved")
        return evaluate_action(
            actor_roles=actor_role_list,
            resource="operational_event",
            action="read",
            organization_id=organization_id,
            verified_conditions=conditions,
        )

    if isinstance(purpose, str) and purpose in SYSTEM_EVENT_PURPOSES:
        if SYSTEM_ADMINISTRATOR not in categories:
            return ActionDecision("deny", "role has no system event visibility")
        allowed_fields = (
            PATIENT_EVENT_METADATA_FIELDS
            if aggregate_type == "patient" or event_type in PATIENT_EVENT_TYPES
            else EVENT_METADATA_FIELDS
        )
        fields = _requested_field_set(requested_fields)
        if fields is None or not fields.issubset(allowed_fields):
            return ActionDecision("deny", "event fields exceed the approved metadata projection")
        if patient_data_redacted:
            conditions.add("patient_data_redacted")
        conditions.add("explicit_admin_purpose")
        return evaluate_action(
            actor_roles=actor_role_list,
            resource="operational_event",
            action="read",
            verified_conditions=conditions,
        )

    return ActionDecision("deny", "event purpose or role is not approved")


def evaluate_event_summary_visibility(
    *,
    actor_roles: Iterable[dict],
    requested_fields: Iterable[str],
    purpose: str,
    organization_id: str | None = None,
    resolved_organization_id: str | None = None,
    event_visibility_approved: bool = False,
    event_payload_redacted: bool = False,
    patient_data_redacted: bool = False,
    audit_recorded: bool = False,
) -> ActionDecision:
    """Authorize queue-wide status counts without event or patient breakdowns."""
    try:
        fields = set(requested_fields)
    except TypeError:
        return ActionDecision("deny", "event summary fields are invalid")
    if not fields or any(not isinstance(field, str) for field in fields):
        return ActionDecision("deny", "event summary fields are invalid")
    if not fields.issubset(EVENT_SUMMARY_FIELDS):
        return ActionDecision("deny", "event summary exposes unapproved fields")

    actor_role_list = tuple(actor_roles)
    categories = {role.get("category") for role in actor_role_list}
    conditions = set()
    if event_visibility_approved:
        conditions.add("event_visibility_approved")
    if event_payload_redacted:
        conditions.add("event_payload_redacted")
    if audit_recorded:
        conditions.add("audit_recorded")

    if purpose == ORGANIZATION_EVENT_PURPOSE:
        if ORGANIZATION_ADMINISTRATOR not in categories:
            return ActionDecision("deny", "role has no organization event visibility")
        if (
            not organization_id
            or not resolved_organization_id
            or str(organization_id) != str(resolved_organization_id)
        ):
            return ActionDecision("deny", "summary is outside the verified organization scope")
        return evaluate_action(
            actor_roles=actor_role_list,
            resource="operational_event",
            action="read",
            organization_id=organization_id,
            verified_conditions=conditions,
        )

    if isinstance(purpose, str) and purpose in SYSTEM_EVENT_PURPOSES:
        if SYSTEM_ADMINISTRATOR not in categories:
            return ActionDecision("deny", "role has no system event visibility")
        if patient_data_redacted:
            conditions.add("patient_data_redacted")
        conditions.add("explicit_admin_purpose")
        return evaluate_action(
            actor_roles=actor_role_list,
            resource="operational_event",
            action="read",
            verified_conditions=conditions,
        )
    return ActionDecision("deny", "event summary purpose or role is not approved")


def evaluate_event_retry(
    *,
    actor_roles: Iterable[dict],
    event_reference: str,
    event_type: str,
    status: str,
    purpose: str,
    reason: str,
    retry_count: int,
    handler_registered: bool,
    handler_retry_safe: bool,
    patient_data_redacted: bool,
    event_payload_redacted: bool,
    audit_recorded: bool,
    bulk_retry: bool = False,
    already_replayed: bool = False,
) -> ActionDecision:
    """Authorize one controlled retry without exposing the event payload."""
    if bulk_retry:
        return ActionDecision("deny", "bulk event retry is not permitted")
    if not isinstance(event_reference, str) or not event_reference.strip():
        return ActionDecision("deny", "an opaque event reference is required")
    if not isinstance(event_type, str) or event_type not in KNOWN_EVENT_TYPES:
        return ActionDecision("deny", "event type is not recognized")
    if not isinstance(status, str) or status not in RETRYABLE_EVENT_STATUSES:
        return ActionDecision("deny", "event state is not eligible for manual retry")
    if not isinstance(retry_count, int) or isinstance(retry_count, bool) or retry_count < 0:
        return ActionDecision("deny", "retry count is invalid")
    if status == "failed" and retry_count >= MAX_MANUAL_RETRY_COUNT:
        return ActionDecision("deny", "failed event has reached the retry limit")
    if status == "dead" and already_replayed:
        return ActionDecision("deny", "dead-letter event has already been replayed")
    if handler_registered is not True or handler_retry_safe is not True:
        return ActionDecision("deny", "event handler is not approved for manual retry")
    if not isinstance(purpose, str) or purpose not in SYSTEM_RETRY_PURPOSES:
        return ActionDecision("deny", "retry purpose is not approved")
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 500:
        return ActionDecision("deny", "a bounded non-empty retry reason is required")

    conditions = {"explicit_admin_purpose", "event_retry_authority"}
    if patient_data_redacted:
        conditions.add("patient_data_redacted")
    if event_payload_redacted:
        conditions.add("event_payload_redacted")
    if audit_recorded:
        conditions.add("audit_recorded")
    return evaluate_action(
        actor_roles=tuple(actor_roles),
        resource="operational_event",
        action="retry",
        verified_conditions=conditions,
    )
