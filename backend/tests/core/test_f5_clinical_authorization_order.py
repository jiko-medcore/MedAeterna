from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.modules.laboratory import service as lab_service
from app.modules.records import service as record_service

PATIENT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
LAB_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
RECORD_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
USER = {"id": "user-1", "roles": []}


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.operation = ""
        self.columns = None
        self.payload = None
        self.filters: dict = {}

    def select(self, columns):
        self.operation = "select"
        self.columns = columns
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def limit(self, _):
        return self

    def execute(self):
        self.client.calls.append({
            "operation": self.operation,
            "table": self.table,
            "columns": self.columns,
            "filters": dict(self.filters),
            "payload": self.payload,
        })
        return FakeResult(self.client.responder(self))


class FakeClient:
    def __init__(self, responder):
        self.responder = responder
        self.calls: list[dict] = []

    def table(self, name):
        return FakeQuery(self, name)


def lab_responder(query: FakeQuery):
    if query.columns == lab_service.LAB_SCOPE_SELECT:
        return [{"id": LAB_ID, "patient_id": PATIENT_ID}]
    return [{
        "id": LAB_ID,
        "patient_id": PATIENT_ID,
        "status": "final",
        "result": "negative",
        "results": None,
        "performed_date": "2026-11-23",
        "created_at": "2026-11-22",
        "ordering_provider": "Dr Synthetic",
        "clinician_id": None,
        "facility_name": "Synthetic Lab",
        "patient_email": "synthetic.patient@example.test",
    }]


def record_responder(query: FakeQuery):
    if query.operation == "update":
        return [{"id": RECORD_ID, "clinical_data": query.payload["clinical_data"]}]
    if query.columns == "id, patient_id":
        return [{"id": RECORD_ID, "patient_id": PATIENT_ID}]
    return [{
        "id": RECORD_ID,
        "patient_id": PATIENT_ID,
        "clinical_data": {"coding": []},
        "summary": "synthetic",
    }]


def test_lab_detail_authorizes_before_clinical_query_and_omits_raw(monkeypatch):
    events: list = []

    def responder(query):
        kind = "query:scope" if query.columns == lab_service.LAB_SCOPE_SELECT else "query:detail"
        events.append(kind)
        return lab_responder(query)

    fake = FakeClient(responder)
    monkeypatch.setattr(lab_service, "supabase_admin", fake)

    def fake_access(patient_id, user):
        events.append("auth")
        assert patient_id == PATIENT_ID
        assert user == USER
        return {}

    monkeypatch.setattr(lab_service, "require_patient_access", fake_access)

    detail = lab_service.build_lab_detail(LAB_ID, USER)

    queries = [call for call in fake.calls if call["operation"] == "select"]
    assert len(queries) == 2
    assert queries[0]["columns"] == lab_service.LAB_SCOPE_SELECT
    assert queries[1]["columns"] == lab_service.LAB_DETAIL_SELECT
    assert events == ["query:scope", "auth", "query:detail"]
    assert "raw" not in detail
    assert "patient_email" not in detail
    assert set(detail) == {"id", "patient_id", "status", "result", "metadata"}


def test_lab_denial_prevents_detailed_clinical_query(monkeypatch):
    fake = FakeClient(lab_responder)
    monkeypatch.setattr(lab_service, "supabase_admin", fake)

    def deny_access(patient_id, user):
        raise HTTPException(status_code=403, detail="Access denied")

    monkeypatch.setattr(lab_service, "require_patient_access", deny_access)

    with pytest.raises(HTTPException) as exc:
        lab_service.build_lab_detail(LAB_ID, USER)

    assert exc.value.status_code == 403
    assert len(fake.calls) == 1
    assert fake.calls[0]["columns"] == lab_service.LAB_SCOPE_SELECT


def test_record_resolution_reauthorizes_before_clinical_fetch(monkeypatch):
    events: list = []

    def responder(query):
        events.append(f"query:{query.operation}")
        return record_responder(query)

    fake = FakeClient(responder)
    monkeypatch.setattr(record_service, "supabase", fake)

    def fake_access(patient_id, user):
        events.append("auth")
        assert patient_id == PATIENT_ID
        return {}

    monkeypatch.setattr(record_service, "require_patient_access", fake_access)

    record_service.resolve_condition_record(RECORD_ID, USER, patient_id=PATIENT_ID)

    select_calls = [call for call in fake.calls if call["operation"] == "select"]
    update_calls = [call for call in fake.calls if call["operation"] == "update"]
    assert events == ["auth", "query:select", "query:update"]
    assert len(select_calls) == 1
    assert "clinical_data" in select_calls[0]["columns"]
    assert select_calls[0]["filters"] == {
        "id": RECORD_ID,
        "patient_id": PATIENT_ID,
        "record_type": "condition",
    }
    assert len(update_calls) == 1
    assert update_calls[0]["filters"] == {
        "id": RECORD_ID,
        "patient_id": PATIENT_ID,
        "record_type": "condition",
    }


def test_record_resolution_without_supplied_patient_uses_minimal_scope_read(monkeypatch):
    fake = FakeClient(record_responder)
    monkeypatch.setattr(record_service, "supabase", fake)
    monkeypatch.setattr(record_service, "require_patient_access", lambda *_: {})

    record_service.resolve_condition_record(RECORD_ID, USER)

    assert fake.calls[0]["columns"] == "id, patient_id"
    assert "clinical_data" not in fake.calls[0]["columns"]


def test_medical_history_projection_does_not_overfetch_rows(monkeypatch):
    fake = FakeClient(lambda query: [])
    monkeypatch.setattr(record_service, "supabase", fake)

    record_service.fetch_medical_records(PATIENT_ID)

    assert len(fake.calls) == 1
    columns = fake.calls[0]["columns"]
    assert "*" not in columns
    assert "clinical_data" not in columns
