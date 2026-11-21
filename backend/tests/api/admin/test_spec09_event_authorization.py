"""PH0-WP-05 / SPEC-09: route-level administrative event authorization tests.

The admin event router is intentionally not mounted by ``main.py`` in this
phase. These tests mount the router on an isolated FastAPI app so the hardened
routes are exercised without widening the deployed HTTP surface.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin import events_router as admin_events
from app.core import operational_event_policy as policy
from app.core import security
from app.core.events import monitoring, replay, service
from app.core.role_catalogue import (
    ORGANIZATION_ADMINISTRATOR,
    PATIENT,
    PRACTITIONER,
    SYSTEM_ADMINISTRATOR,
)


class FakeQuery:
    def __init__(self, client, table, operation="select", payload=None):
        self.client = client
        self.table = table
        self.operation = operation
        self.payload = payload
        self.filters = []
        self.select_fields = None
        self.limit_value = None

    def select(self, fields=None, *args, **kwargs):
        self.select_fields = fields
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def lt(self, key, value):
        self.filters.append((f"<{key}", value))
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def insert(self, payload):
        return FakeQuery(self.client, self.table, "insert", payload)

    def update(self, payload):
        return FakeQuery(self.client, self.table, "update", payload)

    def execute(self):
        self.client.calls.append(
            {
                "operation": self.operation,
                "table": self.table,
                "filters": tuple(self.filters),
                "payload": self.payload,
                "select": self.select_fields,
            }
        )
        rows = self.client.rows.get(self.table, [])
        if self.operation == "select":
            if self.client.select_snapshots:
                rows = self.client.select_snapshots.pop(0)
            matched = [row for row in rows if all(row.get(k) == v for k, v in self.filters)]
            if self.limit_value is not None:
                matched = matched[: self.limit_value]
            return SimpleNamespace(data=matched)
        if self.operation == "insert":
            row = dict(self.payload or {})
            row.setdefault("id", f"new-event-{len(rows) + 1}")
            rows.append(row)
            return SimpleNamespace(data=[row])
        if self.operation == "update":
            matched = [row for row in rows if all(row.get(k) == v for k, v in self.filters)]
            for row in matched:
                row.update(self.payload or {})
            return SimpleNamespace(data=matched if self.select_fields is not None else [])
        raise AssertionError(f"Unexpected operation {self.operation}")


class FakeSupabaseAdmin:
    def __init__(self, rows=None):
        self.rows = rows or {}
        self.calls = []
        self.select_snapshots = []

    def table(self, name):
        return FakeQuery(self, name)


def _user(category, uid="operator-1", org="org-1"):
    return {
        "id": uid,
        "roles": [{"category": category, "organization_id": org if category != SYSTEM_ADMINISTRATOR else None}],
        "organization_ids": [org] if category != SYSTEM_ADMINISTRATOR else [],
    }


def _event_rows():
    return {
        "events": [
            {
                "id": "event-org",
                "aggregate_type": "organization",
                "aggregate_id": "org-1",
                "event_type": "organization.profile.updated",
                "status": "failed",
                "created_at": "2026-11-21T00:00:00+00:00",
                "processed_at": None,
                "retry_count": 1,
                "failure_reason": "Timeout calling dependency for patient@example.com",
                "last_error": None,
                "payload": {"email": "patient@example.com"},
            },
            {
                "id": "event-patient",
                "aggregate_type": "patient",
                "aggregate_id": "patient-1",
                "event_type": "patient.created",
                "status": "failed",
                "created_at": "2026-11-21T00:00:00+00:00",
                "processed_at": None,
                "retry_count": 0,
                "failure_reason": "invalid event",
                "last_error": None,
                "payload": {"email": "patient@example.com"},
            },
        ],
        "events_dead_letter": [
            {
                "id": "dead-1",
                "original_event_id": "event-org",
                "aggregate_type": "organization",
                "aggregate_id": "org-1",
                "event_type": "organization.onboarding.completed",
                "retry_count": 1,
                "failed_at": "2026-11-21T00:00:00+00:00",
                "failure_reason": "Timeout calling dependency",
                "payload": {"email": "patient@example.com"},
                "replayed": False,
            }
        ],
    }


@pytest.fixture
def harness(monkeypatch):
    fake = FakeSupabaseAdmin(_event_rows())
    audit_records = []

    def fake_audit(**kwargs):
        audit_records.append(kwargs)

    monkeypatch.setattr(admin_events, "supabase_admin", fake)
    monkeypatch.setattr(replay, "supabase_admin", fake)
    monkeypatch.setattr(monitoring, "supabase_admin", fake)
    monkeypatch.setattr(service, "supabase_admin", fake)
    monkeypatch.setattr(admin_events, "log_audit_event", fake_audit)
    monkeypatch.setattr(admin_events, "EVENT_HANDLERS", {"organization.onboarding.completed": lambda: None})
    monkeypatch.setattr(
        policy,
        "MANUAL_RETRY_SAFE_EVENT_TYPES",
        frozenset({"organization.onboarding.completed"}),
    )

    app = FastAPI()
    app.include_router(admin_events.router)
    app.include_router(monitoring_router())

    def client_for(user=None):
        app.dependency_overrides.clear()
        if user is not None:
            app.dependency_overrides[security.get_current_user] = lambda: user
        return TestClient(app)

    return fake, audit_records, client_for


def monitoring_router():
    """Expose the internal monitoring helpers through a test-only router."""
    from fastapi import APIRouter

    router = APIRouter(prefix="/internal/events")

    @router.get("/")
    def events():
        return monitoring.get_events()

    @router.get("/dead")
    def dead():
        return monitoring.get_dead_letter_events()

    return router


ADMIN_READ_ROUTES = (
    ("events-list", "get", "/admin/events", {"purpose": "platform_health"}),
    ("stats", "get", "/admin/events/stats", {"purpose": "platform_health"}),
    ("failed", "get", "/admin/events/failed", {"purpose": "platform_health"}),
    ("dead-list", "get", "/admin/events/dead", {"purpose": "platform_health"}),
    ("dead-detail", "get", "/admin/events/dead/dead-1", {"purpose": "platform_health"}),
    ("event-detail", "get", "/admin/events/event-org", {"purpose": "platform_health"}),
)
ADMIN_RETRY_ROUTE = (
    "replay",
    "post",
    "/admin/events/dead/dead-1/replay",
    {"purpose": "event_recovery", "reason": "incident recovery"},
)
ADMIN_ROUTES = ADMIN_READ_ROUTES + (ADMIN_RETRY_ROUTE,)


def _request(client, method, path, params):
    return getattr(client, method)(path, params=params)


@pytest.mark.parametrize(
    "name,method,path,params", ADMIN_ROUTES, ids=[case[0] for case in ADMIN_ROUTES]
)
def test_admin_event_routes_require_authentication(harness, name, method, path, params):
    fake, audit_records, client_for = harness
    with client_for() as client:
        response = _request(client, method, path, params)
    assert response.status_code == 401
    assert fake.calls == []
    assert audit_records == []


def test_all_admin_event_routes_declare_caller_auth_dependency():
    routes = list(admin_events.router.routes)
    assert len(routes) == len(ADMIN_ROUTES)
    for route in routes:
        dependencies = {dependency.call for dependency in route.dependant.dependencies}
        assert security.get_current_user in dependencies, route.path


@pytest.mark.parametrize("category", [PATIENT, PRACTITIONER, ORGANIZATION_ADMINISTRATOR])
def test_non_system_roles_are_denied_before_any_privileged_query(harness, category):
    fake, audit_records, client_for = harness
    with client_for(_user(category)) as client:
        responses = [
            client.get("/admin/events", params={"purpose": "platform_health"}),
            client.get("/admin/events/stats", params={"purpose": "platform_health"}),
            client.get("/admin/events/failed", params={"purpose": "platform_health"}),
            client.get("/admin/events/dead", params={"purpose": "platform_health"}),
            client.get("/admin/events/dead/dead-1", params={"purpose": "platform_health"}),
            client.get("/admin/events/event-org", params={"purpose": "platform_health"}),
            client.post(
                "/admin/events/dead/dead-1/replay",
                params={"purpose": "event_recovery", "reason": "incident recovery"},
            ),
        ]
    assert [response.status_code for response in responses] == [403] * len(responses)
    assert fake.calls == []
    assert audit_records == []


@pytest.mark.parametrize(
    "name,method,path,params", ADMIN_READ_ROUTES, ids=[case[0] for case in ADMIN_READ_ROUTES]
)
def test_read_purpose_allowlist_is_enforced_before_query(harness, name, method, path, params):
    fake, audit_records, client_for = harness
    invalid_params = {**params, "purpose": "event_recovery"}
    with client_for(_user(SYSTEM_ADMINISTRATOR)) as client:
        response = _request(client, method, path, invalid_params)
    assert response.status_code == 400
    assert fake.calls == []
    assert audit_records == []


def test_retry_purpose_allowlist_is_enforced_before_query(harness):
    fake, audit_records, client_for = harness
    with client_for(_user(SYSTEM_ADMINISTRATOR)) as client:
        response = client.post(
            "/admin/events/dead/dead-1/replay",
            params={"purpose": "platform_health", "reason": "incident recovery"},
        )
    assert response.status_code == 400
    assert fake.calls == []
    assert audit_records == []


def test_event_list_projection_is_safe_and_patient_events_are_redacted(harness):
    fake, audit_records, client_for = harness
    with client_for(_user(SYSTEM_ADMINISTRATOR)) as client:
        response = client.get("/admin/events", params={"purpose": "platform_health"})
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 2
    org_row = next(row for row in rows if row["event_reference"] == "event-org")
    patient_row = next(row for row in rows if row["event_reference"] == "event-patient")
    assert org_row["event_type"] == "organization.profile.updated"
    assert org_row["normalized_error_code"] == "DEPENDENCY_TIMEOUT"
    assert "event_type" not in patient_row
    assert patient_row["normalized_error_code"] == "INVALID_EVENT"
    for row in rows:
        assert set(row) <= set(policy.EVENT_METADATA_FIELDS)
        assert "payload" not in row
        assert "aggregate_id" not in row
        assert "failure_reason" not in row
        assert "last_error" not in row
        assert "patient@example.com" not in str(row)
    calls = [call for call in fake.calls if call["table"] == "events"]
    assert calls and all("payload" not in str(call["select"]) for call in calls)
    assert audit_records and all("payload" not in str(record["metadata"]) for record in audit_records)


def test_dead_letter_list_and_detail_share_the_same_projection(harness):
    _, _, client_for = harness
    with client_for(_user(SYSTEM_ADMINISTRATOR)) as client:
        listed = client.get("/admin/events/dead", params={"purpose": "security_incident"})
        detail = client.get(
            "/admin/events/dead/dead-1", params={"purpose": "security_incident"}
        )
    assert listed.status_code == 200
    assert detail.status_code == 200
    assert listed.json() == [detail.json()]
    assert set(detail.json()) <= set(policy.EVENT_METADATA_FIELDS)


def test_retry_denied_until_handler_is_reviewed_retry_safe(harness, monkeypatch):
    fake, audit_records, client_for = harness
    monkeypatch.setattr(policy, "MANUAL_RETRY_SAFE_EVENT_TYPES", frozenset())
    with client_for(_user(SYSTEM_ADMINISTRATOR)) as client:
        response = client.post(
            "/admin/events/dead/dead-1/replay",
            params={"purpose": "event_recovery", "reason": "incident recovery"},
        )
    assert response.status_code == 403
    assert all(call["operation"] == "select" for call in fake.calls)
    assert audit_records == []


def test_retry_rejects_contact_data_in_reason(harness):
    fake, audit_records, client_for = harness
    with client_for(_user(SYSTEM_ADMINISTRATOR)) as client:
        response = client.post(
            "/admin/events/dead/dead-1/replay",
            params={"purpose": "event_recovery", "reason": "contact patient@example.com"},
        )
    assert response.status_code == 400
    assert fake.calls == []
    assert audit_records == []


def test_retry_rejects_empty_reason_before_query(harness):
    fake, audit_records, client_for = harness
    with client_for(_user(SYSTEM_ADMINISTRATOR)) as client:
        response = client.post(
            "/admin/events/dead/dead-1/replay",
            params={"purpose": "event_recovery", "reason": ""},
        )
    assert response.status_code == 422
    assert fake.calls == []
    assert audit_records == []


@pytest.mark.parametrize(
    "name,method,path,params", ADMIN_READ_ROUTES, ids=[case[0] for case in ADMIN_READ_ROUTES]
)
def test_audit_failure_prevents_read_query(harness, monkeypatch, name, method, path, params):
    fake, audit_records, client_for = harness

    def failing_audit(**kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(admin_events, "log_audit_event", failing_audit)
    with client_for(_user(SYSTEM_ADMINISTRATOR)) as client:
        response = _request(client, method, path, params)
    assert response.status_code == 403
    assert fake.calls == []
    assert audit_records == []


def test_audit_failure_prevents_retry(harness, monkeypatch):
    fake, audit_records, client_for = harness

    def failing_audit(**kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(admin_events, "log_audit_event", failing_audit)
    with client_for(_user(SYSTEM_ADMINISTRATOR)) as client:
        response = client.post(
            "/admin/events/dead/dead-1/replay",
            params={"purpose": "event_recovery", "reason": "incident recovery"},
        )
    assert response.status_code == 403
    assert all(call["operation"] == "select" for call in fake.calls)
    assert not any(call["operation"] == "insert" for call in fake.calls)
    assert fake.rows["events_dead_letter"][0]["replayed"] is False
    assert audit_records == []


def test_retry_uses_compare_and_set_and_audits_without_payload(harness):
    fake, audit_records, client_for = harness
    with client_for(_user(SYSTEM_ADMINISTRATOR)) as client:
        response = client.post(
            "/admin/events/dead/dead-1/replay",
            params={"purpose": "event_recovery", "reason": "incident recovery"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "queued"
        assert body["event_reference"] == "new-event-3"
        # Simulate a concurrent operator whose policy read sees a stale row;
        # the compare-and-set claim must still fail.
        fake.select_snapshots = [
            [{**fake.rows["events_dead_letter"][0], "replayed": False}]
        ]
        duplicate = client.post(
            "/admin/events/dead/dead-1/replay",
            params={"purpose": "event_recovery", "reason": "duplicate attempt"},
        )
    assert duplicate.status_code == 409
    updates = [
        call
        for call in fake.calls
        if call["table"] == "events_dead_letter" and call["operation"] == "update"
    ]
    assert updates
    assert ("replayed", False) in updates[0]["filters"]
    assert len([call for call in fake.calls if call["operation"] == "insert"]) == 1
    assert len(audit_records) == 4
    assert all("payload" not in str(record["metadata"]) for record in audit_records)
    assert [record["action"] for record in audit_records] == [
        "EVENT_REPLAY_ATTEMPTED",
        "EVENT_REPLAYED",
        "EVENT_REPLAY_ATTEMPTED",
        "EVENT_REPLAY_DENIED",
    ]
    assert all(record["metadata"]["state_before"] == "dead" for record in audit_records)
    assert audit_records[0]["metadata"]["state_after"] == "pending_if_claim_succeeds"
    assert audit_records[1]["metadata"]["state_after"] == "pending"
    assert audit_records[1]["metadata"]["outcome"] == "queued"
    assert audit_records[3]["metadata"]["outcome"] == "cas_claim_failed"


def test_already_replayed_dead_event_is_denied_by_policy(harness):
    fake, audit_records, client_for = harness
    fake.rows["events_dead_letter"][0]["replayed"] = True
    with client_for(_user(SYSTEM_ADMINISTRATOR)) as client:
        response = client.post(
            "/admin/events/dead/dead-1/replay",
            params={"purpose": "event_recovery", "reason": "incident recovery"},
        )
    assert response.status_code == 403
    assert audit_records == []


def test_legacy_operational_event_routes_stay_disabled(harness, monkeypatch):
    from app.core.events import router as legacy_events

    fake, audit_records, client_for = harness
    app = FastAPI()
    app.include_router(legacy_events.router)
    with TestClient(app) as client:
        responses = [
            client.get("/events/"),
            client.get("/events/failed"),
            client.post("/events/retry-failed"),
            client.get("/events/event-org"),
        ]
    assert [response.status_code for response in responses] == [404, 404, 404, 404]
    assert fake.calls == []
    assert audit_records == []


def test_monitoring_helpers_do_not_select_payloads(harness):
    fake, _, _ = harness
    assert monitoring.get_events()[0]["id"] == "event-org"
    assert monitoring.get_dead_letter_events()[0]["id"] == "dead-1"
    assert [call["table"] for call in fake.calls] == ["events", "events_dead_letter"]
    assert fake.calls[0]["select"] == monitoring.EVENT_METADATA_SELECT
    assert fake.calls[1]["select"] == monitoring.DEAD_LETTER_METADATA_SELECT
    for call in fake.calls:
        assert call["select"] is not None
        assert "*" not in str(call["select"])
        assert "payload" not in str(call["select"])
        assert "failure_reason" not in str(call["select"])


def test_error_text_normalization_never_returns_raw_text():
    assert (
        policy.normalize_event_error_text("Timeout while calling dependency for patient@example.com")
        == "DEPENDENCY_TIMEOUT"
    )
    assert policy.normalize_event_error_text("unexpected sensitive detail") == "PROCESSING_FAILED"
    assert policy.normalize_event_error_text(None) is None


def test_service_retry_requires_failed_state(harness):
    fake, _, _ = harness
    service.EventService.retry_event("event-org")
    assert fake.calls[-1]["filters"] == (
        ("id", "event-org"),
        ("status", "failed"),
        ("<retry_count", 3),
    )
