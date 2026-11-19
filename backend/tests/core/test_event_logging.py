import logging
from types import SimpleNamespace

from app.core.events import emitter
from app.core.events import dispatcher


class FakeEventQuery:
    def __init__(self):
        self.inserted = None

    def insert(self, payload):
        self.inserted = payload
        return self

    def execute(self):
        return SimpleNamespace(data=[{"id": "opaque-event-id"}])


class FakeSupabaseAdmin:
    def __init__(self):
        self.query = FakeEventQuery()

    def table(self, name):
        assert name == "events"
        return self.query


def test_event_emitter_does_not_log_credentials_or_event_identifiers(monkeypatch, caplog):
    fake_client = FakeSupabaseAdmin()
    monkeypatch.setattr(emitter, "supabase_admin", fake_client)
    caplog.set_level(logging.INFO, logger=emitter.logger.name)

    emitter.emit_event(
        aggregate_type="patient",
        aggregate_id="patient-sensitive-id",
        event_type="patient.created",
        payload={"email": "person@example.test", "secret_marker": "do-not-log"},
    )

    assert fake_client.query.inserted["payload"]["secret_marker"] == "do-not-log"
    assert "Operational event emitted" in caplog.text
    for sensitive_value in (
        "patient-sensitive-id",
        "patient.created",
        "person@example.test",
        "do-not-log",
        "SECRET KEY PREFIX",
        "SUPABASE URL",
    ):
        assert sensitive_value not in caplog.text


def test_event_dispatch_does_not_log_event_type_or_identifiers(monkeypatch, caplog):
    monkeypatch.setitem(dispatcher.EVENT_HANDLERS, "patient.created", lambda event: None)
    caplog.set_level(logging.INFO, logger=dispatcher.logger.name)

    dispatcher.dispatch_event(
        {
            "id": "opaque-event-id",
            "aggregate_id": "patient-sensitive-id",
            "event_type": "patient.created",
        }
    )

    assert "Dispatching registered operational event handler" in caplog.text
    assert "opaque-event-id" not in caplog.text
    assert "patient-sensitive-id" not in caplog.text
    assert "patient.created" not in caplog.text


def test_organization_event_handler_does_not_log_organization_identifier(caplog):
    from app.modules.organizations.event_handlers import (
        handle_organization_onboarding_completed,
    )

    caplog.set_level(logging.INFO, logger="app.modules.organizations.event_handlers")
    handle_organization_onboarding_completed({"aggregate_id": "organization-sensitive-id"})

    assert "Organization onboarding completed" in caplog.text
    assert "organization-sensitive-id" not in caplog.text


def test_patient_event_handler_does_not_log_patient_identifier(monkeypatch, caplog):
    from app.modules.patients import event_handlers

    monkeypatch.setattr(event_handlers, "emit_event", lambda **kwargs: None)
    caplog.set_level(logging.INFO, logger=event_handlers.logger.name)

    event_handlers.handle_patient_created(
        {
            "event_type": "patient.created",
            "aggregate_id": "patient-sensitive-id",
            "payload": {"email": "person@example.test"},
        }
    )

    assert "Patient event handler started" in caplog.text
    assert "patient.created" not in caplog.text
    assert "patient-sensitive-id" not in caplog.text
    assert "person@example.test" not in caplog.text
