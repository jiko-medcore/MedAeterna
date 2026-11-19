import pytest

from app.core.events.schemas import EventTypes
from app.core.operational_event_policy import (
    EVENT_METADATA_FIELDS,
    EVENT_SUMMARY_FIELDS,
    KNOWN_EVENT_TYPES,
    NORMALIZED_ERROR_CODES,
    ORGANIZATION_EVENT_PURPOSE,
    PATIENT_EVENT_METADATA_FIELDS,
    SYSTEM_EVENT_PURPOSES,
    evaluate_event_retry,
    evaluate_event_summary_visibility,
    evaluate_event_visibility,
    normalize_event_error_code,
)
from app.core.role_catalogue import (
    ORGANIZATION_ADMINISTRATOR,
    PATIENT,
    PRACTITIONER,
    SYSTEM_ADMINISTRATOR,
)


ORG_ADMIN = [{"category": ORGANIZATION_ADMINISTRATOR, "organization_id": "org-a"}]
SYSTEM_ADMIN = [{"category": SYSTEM_ADMINISTRATOR, "organization_id": None}]
SAFE_FIELDS = {"event_reference", "event_type", "status", "created_at"}


def read_event(**overrides):
    values = {
        "actor_roles": ORG_ADMIN,
        "event_type": "department.updated",
        "aggregate_type": "department",
        "status": "failed",
        "requested_fields": SAFE_FIELDS,
        "purpose": ORGANIZATION_EVENT_PURPOSE,
        "organization_id": "org-a",
        "resolved_organization_id": "org-a",
        "event_payload_redacted": True,
        "event_visibility_approved": True,
        "audit_recorded": True,
    }
    values.update(overrides)
    return evaluate_event_visibility(**values)


def retry_event(**overrides):
    values = {
        "actor_roles": SYSTEM_ADMIN,
        "event_reference": "opaque-event-1",
        "event_type": "patient.created",
        "status": "dead",
        "purpose": "event_recovery",
        "reason": "Confirmed transient dependency issue was resolved.",
        "retry_count": 3,
        "handler_registered": True,
        "handler_retry_safe": True,
        "patient_data_redacted": True,
        "event_payload_redacted": True,
        "audit_recorded": True,
    }
    values.update(overrides)
    return evaluate_event_retry(**values)


def test_event_type_contract_covers_declared_event_types():
    declared_types = {
        value
        for key, value in vars(EventTypes).items()
        if not key.startswith("_") and isinstance(value, str)
    }
    assert declared_types.issubset(KNOWN_EVENT_TYPES)


def test_exception_messages_are_mapped_to_fixed_non_sensitive_error_codes():
    cases = [
        (TimeoutError("patient@example.test"), "DEPENDENCY_TIMEOUT"),
        (ConnectionError("patient id 123"), "DEPENDENCY_UNAVAILABLE"),
        (ValueError("clinical detail"), "INVALID_EVENT"),
        (RuntimeError("raw failure with PHI"), "PROCESSING_FAILED"),
    ]
    for error, code in cases:
        assert normalize_event_error_code(error) == code
        assert code in NORMALIZED_ERROR_CODES
        assert str(error) not in NORMALIZED_ERROR_CODES


def test_org_admin_can_read_allowlisted_event_metadata_in_exact_org():
    result = read_event()
    assert result.allowed

    cross_org = read_event(resolved_organization_id="org-b")
    assert cross_org.decision == "deny"


def test_org_admin_event_read_requires_visibility_payload_redaction_and_audit():
    missing = read_event(
        event_payload_redacted=False,
        event_visibility_approved=False,
        audit_recorded=False,
    )
    assert missing.decision == "conditional"
    assert set(missing.missing_conditions) == {
        "audit_recorded",
        "event_payload_redacted",
        "event_visibility_approved",
    }


def test_org_admin_cannot_read_patient_events_or_raw_event_fields():
    patient_event = read_event(
        event_type="patient.created",
        aggregate_type="patient",
    )
    assert patient_event.decision == "deny"

    for field in ("payload", "aggregate_id", "failure_reason", "last_error", "email"):
        assert read_event(requested_fields={"event_reference", field}).decision == "deny"


def test_org_admin_cannot_read_unmapped_event_types_or_unscoped_events():
    assert read_event(event_type="custom.patient.event").decision == "deny"
    assert read_event(organization_id=None, resolved_organization_id=None).decision == "deny"


@pytest.mark.parametrize("role", [PATIENT, PRACTITIONER])
def test_patient_and_practitioner_roles_cannot_read_admin_event_metadata(role):
    result = read_event(
        actor_roles=[{"category": role, "organization_id": "org-a"}]
    )
    assert result.decision == "deny"


def test_system_admin_can_read_only_redacted_metadata_for_approved_purpose():
    result = read_event(
        actor_roles=SYSTEM_ADMIN,
        event_type="patient.created",
        aggregate_type="patient",
        purpose="security_incident",
        organization_id=None,
        resolved_organization_id=None,
        requested_fields=PATIENT_EVENT_METADATA_FIELDS,
        patient_data_redacted=True,
    )
    assert result.allowed

    for purpose in ("general", "patient_support", ""):
        assert read_event(
            actor_roles=SYSTEM_ADMIN,
            purpose=purpose,
            organization_id=None,
            resolved_organization_id=None,
            patient_data_redacted=True,
        ).decision == "deny"
    assert SYSTEM_EVENT_PURPOSES == {"platform_health", "security_incident"}


def test_system_admin_event_view_requires_both_payload_and_patient_redaction():
    no_redaction = read_event(
        actor_roles=SYSTEM_ADMIN,
        event_type="patient.created",
        aggregate_type="patient",
        purpose="platform_health",
        organization_id=None,
        resolved_organization_id=None,
        requested_fields=PATIENT_EVENT_METADATA_FIELDS,
        event_payload_redacted=False,
        event_visibility_approved=False,
        audit_recorded=False,
    )
    assert no_redaction.decision == "conditional"
    assert set(no_redaction.missing_conditions) == {
        "audit_recorded",
        "event_payload_redacted",
        "event_visibility_approved",
        "patient_data_redacted",
    }

    revealing_event_type = read_event(
        actor_roles=SYSTEM_ADMIN,
        event_type="patient.created",
        aggregate_type="patient",
        purpose="platform_health",
        organization_id=None,
        resolved_organization_id=None,
        requested_fields={"event_reference", "event_type"},
        patient_data_redacted=True,
    )
    assert revealing_event_type.decision == "deny"


def test_system_admin_needs_allowlisted_purpose_for_global_event_read():
    result = read_event(
        actor_roles=SYSTEM_ADMIN,
        organization_id=None,
        resolved_organization_id=None,
        purpose="organization_operations",
        patient_data_redacted=True,
    )
    assert result.decision == "deny"


def test_event_metadata_projection_is_bounded_and_never_includes_raw_errors_or_payload():
    assert "payload" not in EVENT_METADATA_FIELDS
    assert "aggregate_id" not in EVENT_METADATA_FIELDS
    assert "last_error" not in EVENT_METADATA_FIELDS
    assert "failure_reason" not in EVENT_METADATA_FIELDS
    assert "email" not in EVENT_METADATA_FIELDS
    assert "event_type" not in PATIENT_EVENT_METADATA_FIELDS

    for fields in (set(), {"payload"}, {"event_type", "payload"}):
        assert read_event(requested_fields=fields).decision == "deny"


def test_event_summary_is_aggregate_only_and_organization_scoped():
    summary = evaluate_event_summary_visibility(
        actor_roles=ORG_ADMIN,
        requested_fields=EVENT_SUMMARY_FIELDS,
        purpose=ORGANIZATION_EVENT_PURPOSE,
        organization_id="org-a",
        resolved_organization_id="org-a",
        event_visibility_approved=True,
        event_payload_redacted=True,
        audit_recorded=True,
    )
    assert summary.allowed

    assert evaluate_event_summary_visibility(
        actor_roles=ORG_ADMIN,
        requested_fields={"total", "patient_ids"},
        purpose=ORGANIZATION_EVENT_PURPOSE,
        organization_id="org-a",
        resolved_organization_id="org-a",
        event_visibility_approved=True,
        event_payload_redacted=True,
        audit_recorded=True,
    ).decision == "deny"
    assert evaluate_event_summary_visibility(
        actor_roles=ORG_ADMIN,
        requested_fields={"total"},
        purpose=ORGANIZATION_EVENT_PURPOSE,
        organization_id="org-a",
        resolved_organization_id="org-b",
        event_visibility_approved=True,
        event_payload_redacted=True,
        audit_recorded=True,
    ).decision == "deny"


def test_system_admin_can_retry_one_safe_event_after_authority_and_audit_checks():
    assert retry_event().allowed


def test_org_admin_patient_and_practitioner_cannot_retry_events():
    for role in (
        {"category": ORGANIZATION_ADMINISTRATOR, "organization_id": "org-a"},
        {"category": PATIENT, "organization_id": None},
        {"category": PRACTITIONER, "organization_id": "org-a"},
    ):
        assert retry_event(actor_roles=[role]).decision == "deny"


@pytest.mark.parametrize("status", ["pending", "processing", "processed", "unknown"])
def test_nonfailed_or_non_dead_event_states_cannot_be_manually_retried(status):
    assert retry_event(status=status).decision == "deny"


def test_bulk_retry_and_replayed_dead_letter_retry_deny():
    assert retry_event(bulk_retry=True).decision == "deny"
    assert retry_event(already_replayed=True).decision == "deny"


def test_failed_event_at_or_over_retry_limit_cannot_be_retried():
    assert retry_event(status="failed", retry_count=3).decision == "deny"
    assert retry_event(status="failed", retry_count=2).allowed


@pytest.mark.parametrize(
    "overrides",
    [
        {"handler_registered": False},
        {"handler_retry_safe": False},
        {"purpose": "general"},
        {"reason": ""},
        {"reason": "   "},
        {"reason": "x" * 501},
        {"event_reference": ""},
        {"event_type": "unregistered.event"},
        {"retry_count": -1},
    ],
)
def test_retry_requires_registered_safe_handler_reason_and_valid_event(overrides):
    assert retry_event(**overrides).decision == "deny"


def test_missing_redaction_and_audit_do_not_authorize_retry():
    result = retry_event(
        patient_data_redacted=False,
        event_payload_redacted=False,
        audit_recorded=False,
    )
    assert result.decision == "conditional"
    assert set(result.missing_conditions) == {
        "audit_recorded",
        "event_payload_redacted",
        "patient_data_redacted",
    }
