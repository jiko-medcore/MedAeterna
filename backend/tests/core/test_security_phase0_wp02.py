"""PH0-WP-02: clinical route/resource authorization tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core import clinical_authorization as clinical
from app.core import security
from app.core.role_catalogue import (
    ORGANIZATION_ADMINISTRATOR,
    PATIENT,
    PRACTITIONER,
    SYSTEM_ADMINISTRATOR,
)
from app.modules.appointments import router as appointment_router
from app.modules.care_team import router as care_team_router
from app.modules.medications import router as medication_router
from app.modules.observations import router as observation_router
from main import app


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.filters = []
        self._single = None

    def select(self, *args, **kwargs):
        return self

    def eq(self, key, value):
        self.filters.append(("eq", key, value))
        return self

    def is_(self, key, value):
        self.filters.append(("is", key, value))
        return self

    def limit(self, n):
        return self

    def single(self):
        self._single = True
        return self

    def execute(self):
        key = (self.table, tuple(sorted(self.filters)))
        rows = self.client.responses.get(key, [])
        data = rows[0] if rows and self._single else (None if self._single else rows)
        return SimpleNamespace(data=data)


class FakeSupabaseAdmin:
    def __init__(self, responses):
        self.responses = responses

    def table(self, name):
        return FakeQuery(self, name)


def _patient_user(uid="patient-1", org=None):
    return {"id": uid, "roles": [{"category": PATIENT, "organization_id": org}]}


def _practitioner_user(uid="user-prac-1", org="org-1"):
    return {
        "id": uid,
        "roles": [{"category": PRACTITIONER, "organization_id": org}],
        "organization_ids": [org],
    }


def _org_admin_user(uid="admin-1", org="org-1"):
    return {
        "id": uid,
        "roles": [{"category": ORGANIZATION_ADMINISTRATOR, "organization_id": org}],
        "organization_ids": [org],
    }


def _system_admin(uid="admin-1"):
    return {"id": uid, "roles": [{"category": SYSTEM_ADMINISTRATOR, "organization_id": None}]}


def _patient_row(org="org-1"):
    return {
        ("patients", (("eq", "id", "patient-1"),)): [
            {"id": "patient-1", "organization_id": org}
        ]
    }


def _practitioner_rows(practitioner_id="prac-1"):
    return {
        ("practitioners", (("eq", "id", "user-prac-1"),)): [],
        ("practitioners", (("eq", "profile_id", "user-prac-1"),)): [
            {"id": practitioner_id, "profile_id": "user-prac-1"}
        ],
    }


def _care_team_row(patient="patient-1", practitioner="prac-1", org="org-1"):
    return {
        (
            "patient_care_team",
            (
                ("eq", "organization_id", org),
                ("eq", "patient_id", patient),
                ("eq", "practitioner_id", practitioner),
                ("eq", "status", "active"),
            ),
        ): [{
            "id": "ct-1", "patient_id": patient, "practitioner_id": practitioner,
            "organization_id": org, "status": "active", "start_date": None, "end_date": None,
        }]
    }


def test_patient_self_can_read_clinical_record(monkeypatch):
    monkeypatch.setattr(security, "supabase_admin", FakeSupabaseAdmin(_patient_row()))
    context = clinical.authorize_clinical_access(
        _patient_user(),
        resource=clinical.CLINICAL_RECORD,
        action="read",
        patient_id="patient-1",
        organization_id="org-1",
        verified_conditions={"clinical_workflow"},
    )
    assert context["authorized_patient_id"] == "patient-1"
    assert context["authorized_action"] == "read"


def test_patient_self_cannot_create_clinical_record(monkeypatch):
    monkeypatch.setattr(security, "supabase_admin", FakeSupabaseAdmin(_patient_row()))
    with pytest.raises(HTTPException) as exc:
        clinical.authorize_clinical_access(
            _patient_user(),
            resource=clinical.CLINICAL_RECORD,
            action="create",
            patient_id="patient-1",
            organization_id="org-1",
            verified_conditions={"clinical_workflow"},
        )
    assert exc.value.status_code == 403


def test_practitioner_with_care_relationship_can_read(monkeypatch):
    responses = _patient_row()
    responses.update(_practitioner_rows())
    responses.update(_care_team_row())
    monkeypatch.setattr(security, "supabase_admin", FakeSupabaseAdmin(responses))
    context = clinical.authorize_clinical_access(
        _practitioner_user(),
        resource=clinical.CLINICAL_RECORD,
        action="read",
        patient_id="patient-1",
        organization_id="org-1",
        verified_conditions={"clinical_workflow"},
    )
    assert context["authorized_practitioner_id"] == "prac-1"


def test_practitioner_without_relationship_is_denied(monkeypatch):
    responses = _patient_row()
    responses.update(_practitioner_rows())
    monkeypatch.setattr(security, "supabase_admin", FakeSupabaseAdmin(responses))
    with pytest.raises(HTTPException) as exc:
        clinical.authorize_clinical_access(
            _practitioner_user(),
            resource=clinical.CLINICAL_RECORD,
            action="read",
            patient_id="patient-1",
            organization_id="org-1",
            verified_conditions={"clinical_workflow"},
        )
    assert exc.value.status_code == 403


def test_cross_organization_practitioner_is_denied(monkeypatch):
    monkeypatch.setattr(
        security, "supabase_admin", FakeSupabaseAdmin(_patient_row())
    )
    with pytest.raises(HTTPException) as exc:
        clinical.authorize_clinical_access(
            _practitioner_user(org="org-2"),
            resource=clinical.CLINICAL_RECORD,
            action="read",
            patient_id="patient-1",
            organization_id="org-2",
            verified_conditions={"clinical_workflow"},
        )
    assert exc.value.status_code == 404


def test_system_admin_denied_clinical_record(monkeypatch):
    monkeypatch.setattr(
        security, "supabase_admin", FakeSupabaseAdmin(_patient_row())
    )
    with pytest.raises(HTTPException):
        clinical.authorize_clinical_access(
            _system_admin(),
            resource=clinical.CLINICAL_RECORD,
            action="read",
            patient_id="patient-1",
            organization_id="org-1",
        )


def test_org_admin_can_read_care_team_in_own_org(monkeypatch):
    monkeypatch.setattr(
        security, "supabase_admin", FakeSupabaseAdmin(_patient_row())
    )
    context = clinical.authorize_patient_scoped_access(
        _org_admin_user(),
        resource=clinical.CARE_TEAM,
        action="read",
        patient_id="patient-1",
        organization_id="org-1",
        allow_organization_admin=True,
        organization_care_authority=True,
    )
    assert context["authorized_organization_id"] == "org-1"


def test_org_admin_cannot_read_care_team_in_other_org(monkeypatch):
    monkeypatch.setattr(
        security, "supabase_admin", FakeSupabaseAdmin(_patient_row())
    )
    with pytest.raises(HTTPException) as exc:
        clinical.authorize_patient_scoped_access(
            _org_admin_user(org="org-2"),
            resource=clinical.CARE_TEAM,
            action="read",
            patient_id="patient-1",
            organization_id="org-2",
            allow_organization_admin=True,
            organization_care_authority=True,
        )
    assert exc.value.status_code == 404


def test_appointment_read_requires_assigned_practitioner(monkeypatch):
    responses = {
        ("appointments", (("eq", "id", "appt-1"),)): [
            {
                "id": "appt-1",
                "patient_id": "patient-1",
                "organization_id": "org-1",
                "practitioner_id": "prac-2",
                "status": "booked",
            }
        ]
    }
    responses.update(_patient_row())
    responses.update(_practitioner_rows())
    responses.update(_care_team_row())
    monkeypatch.setattr(security, "supabase_admin", FakeSupabaseAdmin(responses))
    with pytest.raises(HTTPException) as exc:
        clinical.authorize_table_access(
            _practitioner_user(), "appointments", "appt-1", "read"
        )
    assert exc.value.status_code == 403


def test_appointment_read_allowed_for_assigned_practitioner(monkeypatch):
    responses = {
        ("appointments", (("eq", "id", "appt-1"),)): [
            {
                "id": "appt-1",
                "patient_id": "patient-1",
                "organization_id": "org-1",
                "practitioner_id": "prac-1",
                "status": "booked",
            }
        ]
    }
    responses.update(_patient_row())
    responses.update(_practitioner_rows())
    responses.update(_care_team_row())
    monkeypatch.setattr(security, "supabase_admin", FakeSupabaseAdmin(responses))
    context = clinical.authorize_table_access(
        _practitioner_user(), "appointments", "appt-1", "read"
    )
    assert context["authorized_resource_id"] == "appt-1"


def test_service_rejects_missing_or_mismatched_context(monkeypatch):
    from app.modules.medications.service import get_encounter_medication

    monkeypatch.setattr(
        "app.modules.medications.service.supabase_admin", FakeSupabaseAdmin({})
    )
    with pytest.raises(HTTPException):
        get_encounter_medication("enc-1", authorized_context={})
    with pytest.raises(HTTPException):
        get_encounter_medication(
            "enc-1",
            authorized_context={
                "authorized_resource": clinical.CLINICAL_RECORD,
                "authorized_action": "read",
                "authorized_user_id": "patient-1",
                "authorized_resource_id": "enc-2",
            },
        )


def _client():
    app.dependency_overrides.clear()
    return TestClient(app)


def test_medication_encounter_route_requires_authentication(monkeypatch):
    called = []
    monkeypatch.setattr(
        medication_router,
        "get_encounter_medication",
        lambda encounter_id, authorized_context: called.append(encounter_id) or ["ok"],
    )
    with _client() as client:
        response = client.get("/medication-requests/encounter/enc-1")
    assert response.status_code == 401
    assert called == []


def test_medication_encounter_route_allows_verified_patient(monkeypatch):
    responses = {
        ("encounters", (("eq", "id", "enc-1"),)): [
            {"id": "enc-1", "patient_id": "patient-1", "organization_id": "org-1"}
        ],
        **_patient_row(),
    }
    monkeypatch.setattr(security, "supabase_admin", FakeSupabaseAdmin(responses))
    called = []
    monkeypatch.setattr(
        medication_router,
        "get_encounter_medication",
        lambda encounter_id, authorized_context: called.append(encounter_id) or ["ok"],
    )
    with _client() as client:
        app.dependency_overrides[security.get_current_user] = lambda: _patient_user()
        response = client.get("/medication-requests/encounter/enc-1")
    assert response.status_code == 200
    assert response.json() == ["ok"]
    assert called == ["enc-1"]


def test_medication_encounter_route_denies_unrelated_practitioner_before_service(monkeypatch):
    responses = {
        ("encounters", (("eq", "id", "enc-1"),)): [
            {"id": "enc-1", "patient_id": "patient-1", "organization_id": "org-1"}
        ],
        **_patient_row(),
    }
    responses.update(_practitioner_rows())
    monkeypatch.setattr(security, "supabase_admin", FakeSupabaseAdmin(responses))
    called = []
    monkeypatch.setattr(
        medication_router,
        "get_encounter_medication",
        lambda encounter_id, authorized_context: called.append(encounter_id) or ["ok"],
    )
    with _client() as client:
        app.dependency_overrides[security.get_current_user] = lambda: _practitioner_user()
        response = client.get("/medication-requests/encounter/enc-1")
    assert response.status_code == 403
    assert called == []


def test_observation_encounter_route_denies_cross_patient_practitioner(monkeypatch):
    responses = {
        ("encounters", (("eq", "id", "enc-2"),)): [
            {"id": "enc-2", "patient_id": "patient-2", "organization_id": "org-1"}
        ],
        ("patients", (("eq", "id", "patient-2"),)): [
            {"id": "patient-2", "organization_id": "org-1"}
        ],
    }
    responses.update(_practitioner_rows())
    monkeypatch.setattr(security, "supabase_admin", FakeSupabaseAdmin(responses))
    called = []
    monkeypatch.setattr(
        observation_router,
        "get_encounter_observations",
        lambda encounter_id, authorized_context: called.append(encounter_id) or ["ok"],
    )
    with _client() as client:
        app.dependency_overrides[security.get_current_user] = lambda: _practitioner_user()
        response = client.get("/observations/encounter/enc-2")
    assert response.status_code == 403
    assert called == []


def test_practitioner_schedule_route_denies_other_practitioner(monkeypatch):
    monkeypatch.setattr(
        security, "supabase_admin", FakeSupabaseAdmin(_practitioner_rows())
    )
    called = []
    monkeypatch.setattr(
        appointment_router,
        "get_practitioner_appointments",
        lambda practitioner_id, authorized_context: called.append(practitioner_id) or ["ok"],
    )
    with _client() as client:
        app.dependency_overrides[security.get_current_user] = lambda: _practitioner_user()
        app.dependency_overrides[security.require_practitioner] = lambda: {"id": "prac-2"}
        response = client.get("/appointments/practitioner/prac-2")
    assert response.status_code == 403
    assert called == []


def test_patient_cannot_create_care_team(monkeypatch):
    monkeypatch.setattr(security, "supabase_admin", FakeSupabaseAdmin(_patient_row()))
    called = []
    monkeypatch.setattr(
        care_team_router,
        "create_care_team",
        lambda payload, authorized_context: called.append(payload) or {"id": "ct-1"},
    )
    with _client() as client:
        app.dependency_overrides[security.get_current_user] = lambda: _patient_user()
        response = client.post(
            "/care-teams/",
            json={"patient_id": "patient-1", "organization_id": "org-1"},
        )
    assert response.status_code == 403
    assert called == []
