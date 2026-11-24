from __future__ import annotations

from dataclasses import dataclass

from app.core.audit import service as audit_service
from app.core.events import dead_letter, state

EVENT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
PATIENT_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


@dataclass
class Call:
    table: str
    operation: str
    payload: dict | None


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, fake, table):
        self.fake = fake
        self.table = table
        self.operation = ""
        self.payload = None

    def select(self, _columns):
        self.operation = "select"
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def eq(self, _column, _value):
        return self

    def limit(self, _):
        return self

    def single(self):
        return self

    def execute(self):
        self.fake.calls.append(Call(self.table, self.operation, self.payload))
        if self.operation == "select" and self.table == "events":
            return FakeResult({
                "id": EVENT_ID,
                "event_type": "PATIENT_CREATED",
                "aggregate_type": "patient",
                "aggregate_id": PATIENT_ID,
                "payload": {"patient_id": PATIENT_ID},
                "retry_count": 2,
            })
        return FakeResult([{"id": "row-1"}])


class FakeSupabaseAdmin:
    def __init__(self):
        self.calls: list[Call] = []

    def table(self, name):
        return FakeQuery(self, name)


def test_mark_failed_preserves_dlq_provenance_and_audit_reference(monkeypatch):
    fake = FakeSupabaseAdmin()
    monkeypatch.setattr(state, "supabase_admin", fake)
    monkeypatch.setattr(dead_letter, "supabase_admin", fake)
    monkeypatch.setattr(audit_service, "supabase_admin", fake)

    state.mark_failed(EVENT_ID, "handler_error")

    dlq = next(call for call in fake.calls if call.table == "events_dead_letter")
    assert dlq.operation == "insert"
    assert dlq.payload["original_event_id"] == EVENT_ID
    assert dlq.payload["aggregate_type"] == "patient"
    assert dlq.payload["aggregate_id"] == PATIENT_ID
    assert dlq.payload["event_type"] == "PATIENT_CREATED"
    assert dlq.payload["payload"] == {"patient_id": PATIENT_ID}
    assert dlq.payload["retry_count"] == 3

    audit = next(call for call in fake.calls if call.table == "audit_logs")
    assert audit.payload["resource_id"] == EVENT_ID
    assert audit.payload["metadata"]["retry_count"] == 3
