from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.core import clinical_authorization
from app.core.clinical_authorization import CLINICAL_RECORD
from app.core.role_catalogue import PATIENT, PRACTITIONER
from app.modules.laboratory import service as lab_service
from app.modules.records import service as record_service
from app.modules.patients import service as patient_service

PATIENT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
LAB_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
RECORD_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"


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

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def limit(self, _):
        return self

    def execute(self):
        call = {
            "operation": self.operation,
            "table": self.table,
            "columns": self.columns,
            "filters": dict(self.filters),
            "payload": self.payload,
        }
        self.client.calls.append(call)
        return FakeResult(self.client.responder(self))


class FakeClient:
    def __init__(self, responder):
        self.responder = responder
        self.calls: list[dict] = []

    def table(self, name):
        return FakeQuery(self, name)


def authorized_context(*, action="read", patient_id=PATIENT_ID, resource_id=LAB_ID):
    return {
        "authorized_user_id": "patient-user-1",
        "authorized_resource": CLINICAL_RECORD,
        "authorized_action": action,
        "authorized_patient_id": patient_id,
        "authorized_organization_id": "org-1",
        "authorized_resource_id": resource_id,
    }


def lab_responder(query: FakeQuery):
    return [{
        "id": LAB_ID,
        "patient_id": PATIENT_ID,
        "status": "completed",
        "result_data": "negative",
        "performed_at": "2026-11-23",
        "created_at": "2026-11-22",
        "clinician_id": "synthetic-clinician",
        "patient_email": "synthetic.patient@example.test",
    }]


def record_responder(query: FakeQuery):
    if query.operation == "update":
        return [{
            "id": RECORD_ID,
            "patient_id": PATIENT_ID,
            "clinical_data": query.payload["clinical_data"],
        }]
    if query.operation == "insert":
        return [{"id": RECORD_ID, **query.payload}]
    return [{
        "id": RECORD_ID,
        "patient_id": PATIENT_ID,
        "clinical_data": {"clinicalStatus": {"coding": []}},
        "summary": "synthetic",
    }]


def test_lab_detail_requires_explicit_context_before_detail_query(monkeypatch):
    fake = FakeClient(lab_responder)
    monkeypatch.setattr(lab_service, "supabase_admin", fake)

    with pytest.raises(HTTPException) as exc:
        lab_service.build_lab_detail(LAB_ID, authorized_context=None)

    assert exc.value.status_code == 403
    assert fake.calls == []


def test_lab_detail_filters_by_authorized_resource_and_patient(monkeypatch):
    fake = FakeClient(lab_responder)
    monkeypatch.setattr(lab_service, "supabase_admin", fake)

    detail = lab_service.build_lab_detail(
        LAB_ID,
        authorized_context=authorized_context(),
    )

    assert len(fake.calls) == 1
    assert fake.calls[0]["table"] == "lab_results"
    assert fake.calls[0]["columns"] == lab_service.LAB_DETAIL_SELECT
    assert fake.calls[0]["filters"] == {"id": LAB_ID, "patient_id": PATIENT_ID}
    assert "raw" not in detail
    assert "patient_email" not in detail
    assert set(detail) == {"id", "patient_id", "status", "result", "metadata"}


def test_lab_detail_rejects_resource_id_mismatch_before_query(monkeypatch):
    fake = FakeClient(lab_responder)
    monkeypatch.setattr(lab_service, "supabase_admin", fake)

    with pytest.raises(HTTPException) as exc:
        lab_service.build_lab_detail(
            LAB_ID,
            authorized_context=authorized_context(resource_id="different-lab"),
        )

    assert exc.value.status_code == 403
    assert fake.calls == []


def test_condition_resolution_requires_authorized_stored_resource_context(monkeypatch):
    fake = FakeClient(record_responder)
    monkeypatch.setattr(record_service, "supabase_admin", fake)

    context = authorized_context(
        action="update",
        resource_id=RECORD_ID,
    )
    context["resource_row"] = {
        "id": RECORD_ID,
        "patient_id": PATIENT_ID,
        "record_type": "condition",
    }

    result = record_service.resolve_condition_record(
        RECORD_ID,
        authorized_context=context,
    )

    assert result["id"] == RECORD_ID
    assert [call["operation"] for call in fake.calls] == ["select", "update"]
    assert fake.calls[0]["filters"] == {
        "id": RECORD_ID,
        "patient_id": PATIENT_ID,
        "record_type": "condition",
    }
    assert fake.calls[1]["filters"] == {
        "id": RECORD_ID,
        "patient_id": PATIENT_ID,
        "record_type": "condition",
    }
    assert fake.calls[1]["payload"]["updated_by"] == "patient-user-1"


def test_condition_resolution_denies_missing_context_before_query(monkeypatch):
    fake = FakeClient(record_responder)
    monkeypatch.setattr(record_service, "supabase_admin", fake)

    with pytest.raises(HTTPException) as exc:
        record_service.resolve_condition_record(
            RECORD_ID,
            authorized_context=None,
        )

    assert exc.value.status_code == 403
    assert fake.calls == []


def test_condition_resolution_rejects_mismatched_stored_resource_before_query(monkeypatch):
    fake = FakeClient(record_responder)
    monkeypatch.setattr(record_service, "supabase_admin", fake)
    context = authorized_context(action="update", resource_id=RECORD_ID)
    context["resource_row"] = {
        "id": RECORD_ID,
        "patient_id": "other-patient",
        "record_type": "condition",
    }

    with pytest.raises(HTTPException) as exc:
        record_service.resolve_condition_record(
            RECORD_ID,
            authorized_context=context,
        )

    assert exc.value.status_code == 403
    assert fake.calls == []


def test_create_legacy_record_requires_context_before_insert(monkeypatch):
    fake = FakeClient(record_responder)
    monkeypatch.setattr(record_service, "supabase_admin", fake)
    payload = SimpleNamespace(
        patient_id=PATIENT_ID,
        record_type="observation",
        clinical_data={"resourceType": "Observation"},
    )

    with pytest.raises(HTTPException) as exc:
        record_service.create_record(payload, authorized_context=None)

    assert exc.value.status_code == 403
    assert fake.calls == []


def test_create_legacy_record_binds_clinician_to_authorized_actor(monkeypatch):
    fake = FakeClient(record_responder)
    monkeypatch.setattr(record_service, "supabase_admin", fake)
    payload = SimpleNamespace(
        patient_id=PATIENT_ID,
        record_type="observation",
        clinical_data={"resourceType": "Observation"},
    )

    record_service.create_record(
        payload,
        authorized_context=authorized_context(action="create"),
    )

    assert len(fake.calls) == 1
    assert fake.calls[0]["operation"] == "insert"
    assert fake.calls[0]["payload"]["clinician_id"] == "patient-user-1"
    assert fake.calls[0]["payload"]["patient_id"] == PATIENT_ID


def test_medical_history_projection_requires_context_and_does_not_overfetch(monkeypatch):
    fake = FakeClient(lambda query: [])
    monkeypatch.setattr(record_service, "supabase_admin", fake)

    with pytest.raises(HTTPException):
        record_service.fetch_medical_records(PATIENT_ID, authorized_context=None)
    assert fake.calls == []

    record_service.fetch_medical_records(
        PATIENT_ID,
        authorized_context=authorized_context(),
    )

    assert len(fake.calls) == 1
    columns = fake.calls[0]["columns"]
    assert columns == "id, created_at, record_type"
    assert fake.calls[0]["filters"] == {"patient_id": PATIENT_ID}



@pytest.mark.parametrize(
    "service_call",
    [
        lambda: patient_service.get_patient_summary(PATIENT_ID, authorized_context=None),
        lambda: patient_service.get_patient_with_records(PATIENT_ID, authorized_context=None),
        lambda: patient_service.build_patient_timeline(
            UUID(PATIENT_ID),
            authorized_context=None,
        ),
    ],
)
def test_patient_record_services_deny_missing_context_before_query(monkeypatch, service_call):
    fake = FakeClient(lambda _query: [])
    monkeypatch.setattr(patient_service, "supabase", fake)

    with pytest.raises(HTTPException) as exc:
        service_call()

    assert exc.value.status_code == 403
    assert fake.calls == []



def test_lab_result_policy_uses_lab_resource_family_and_keeps_consent_separate(monkeypatch):
    practitioner = {
        "id": "practitioner-user-1",
        "roles": [{"category": PRACTITIONER, "organization_id": "org-1"}],
    }
    monkeypatch.setattr(
        clinical_authorization.security,
        "fetch_resource",
        lambda *_args, **_kwargs: {
            "id": LAB_ID,
            "patient_id": PATIENT_ID,
            "clinician_id": "practitioner-1",
        },
    )
    relationship_calls = []

    def fake_patient_access(_user, _patient_id, **kwargs):
        relationship_calls.append(kwargs)
        return {"authorized_organization_id": "org-1"}

    monkeypatch.setattr(
        clinical_authorization.security,
        "authorize_patient_access",
        fake_patient_access,
    )

    with pytest.raises(HTTPException) as exc:
        clinical_authorization.authorize_table_access(
            practitioner,
            "lab_results",
            LAB_ID,
            "read",
        )

    assert relationship_calls[0]["resource_family"] == "lab_result"
    assert "consent_if_required" in str(exc.value.detail)


def test_patient_self_can_read_own_lab_result_with_verified_identity(monkeypatch):
    patient = {
        "id": PATIENT_ID,
        "roles": [{"category": PATIENT, "organization_id": "org-1"}],
    }
    monkeypatch.setattr(
        clinical_authorization.security,
        "fetch_resource",
        lambda *_args, **_kwargs: {
            "id": LAB_ID,
            "patient_id": PATIENT_ID,
            "clinician_id": "practitioner-1",
        },
    )
    relationship_calls = []

    def fake_patient_access(_user, _patient_id, **kwargs):
        relationship_calls.append(kwargs)
        return {"authorized_patient_id": PATIENT_ID, "authorized_organization_id": "org-1"}

    monkeypatch.setattr(
        clinical_authorization.security,
        "authorize_patient_access",
        fake_patient_access,
    )

    context = clinical_authorization.authorize_table_access(
        patient,
        "lab_results",
        LAB_ID,
        "read",
    )

    assert relationship_calls[0]["resource_family"] == "lab_result"
    assert context["authorized_patient_id"] == PATIENT_ID
    assert context["authorized_resource_id"] == LAB_ID
    assert context["authorized_action"] == "read"
