"""Order 9: route-by-route clinical authorization evidence.

All evidence in this module is local and synthetic. It patches both
``app.core.security.supabase_admin`` and module-level service clients before any
call that could reach a hosted project. No production data, credential, or
service-role write is used.
"""

from __future__ import annotations

import re
from pathlib import Path
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
from app.modules.appointments import service as appointment_service
from app.modules.care_team import router as care_team_router
from app.modules.care_team import service as care_team_service
from app.modules.conditions import router as condition_router
from app.modules.encounters import router as encounter_router
from app.modules.laboratory import service as lab_service
from app.modules.medications import router as medication_router
from app.modules.observations import router as observation_router
from app.modules.patients import router as patients_router
from app.modules.patients import service as patients_service
from app.modules.records import router as records_router
from main import app


PATIENT_UUID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


SENSITIVE_ROUTES = frozenset({
    ("GET", "/patients/medical-id"),
    ("GET", "/patients/me"),
    ("GET", "/patients/profile/me"),
    ("GET", "/patients/mine"),
    ("PUT", "/patients/profile/me"),
    ("GET", "/patients/{patient_id}/fhir"),
    ("GET", "/patients/{patient_id}/qr"),
    ("GET", "/patients/{patient_id}/summary"),
    ("GET", "/patients/{patient_id}/timeline"),
    ("POST", "/patients/{patient_id}/assign"),
    ("POST", "/patients/profile/upload-avatar"),
    ("POST", "/records/observations"),
    ("POST", "/records/conditions"),
    ("POST", "/records/medications"),
    ("PATCH", "/records/conditions/{record_id}/resolve"),
    ("POST", "/care-teams/"),
    ("POST", "/care-teams/{care_team_id}/participants"),
    ("GET", "/care-teams/patient/{patient_id}"),
    ("PATCH", "/care-teams/participants/{participant_id}"),
    ("POST", "/care-teams/assign"),
    ("POST", "/consents/grant"),
    ("POST", "/consents/revoke"),
    ("GET", "/consents/me"),
    ("POST", "/encounters/"),
    ("GET", "/encounters/patient/{patient_id}"),
    ("PATCH", "/encounters/{encounter_id}"),
    ("POST", "/observations/"),
    ("GET", "/observations/patient/{patient_id}"),
    ("GET", "/observations/encounter/{encounter_id}"),
    ("PATCH", "/observations/{observation_id}"),
    ("POST", "/conditions/"),
    ("GET", "/conditions/patient/{patient_id}"),
    ("GET", "/conditions/encounter/{encounter_id}"),
    ("PATCH", "/conditions/{condition_id}"),
    ("POST", "/medication-requests/"),
    ("GET", "/medication-requests/patient/{patient_id}"),
    ("GET", "/medication-requests/encounter/{encounter_id}"),
    ("PATCH", "/medication-requests/{medication_request_id}"),
    ("POST", "/appointments/"),
    ("GET", "/appointments/patient/{patient_id}"),
    ("GET", "/appointments/practitioner/{practitioner_id}"),
    ("PATCH", "/appointments/{appointment_id}"),
    ("GET", "/api/v1/medical-history"),
    ("GET", "/api/v1/lab-results/{lab_id}"),
    ("GET", "/api/v1/user/summary"),
})


def _key(table: str, **filters) -> tuple:
    return (table, tuple(sorted((key, value) for key, value in filters.items())))


class FakeQuery:
    def __init__(self, client: "FakeAdmin", table: str):
        self.client = client
        self.table = table
        self.operation = "select"
        self.columns = None
        self.payload = None
        self.filters: dict = {}
        self._single = False

    def select(self, columns="*"):
        self.operation = "select"
        self.columns = columns
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def upsert(self, payload):
        self.operation = "upsert"
        self.payload = payload
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def is_(self, key, value):
        self.filters[key] = value
        return self

    def in_(self, key, values):
        self.filters[key] = tuple(values)
        return self

    def gte(self, key, value):
        self.filters[key] = ("gte", value)
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, _value):
        return self

    def single(self):
        self._single = True
        return self

    def execute(self):
        key = (
            self.table,
            tuple(sorted((name, value) for name, value in self.filters.items())),
        )
        rows = self.client.responses.get(key, self.client.defaults.get(self.table, []))
        self.client.calls.append({
            "operation": self.operation,
            "table": self.table,
            "columns": self.columns,
            "filters": dict(self.filters),
            "payload": self.payload,
        })
        data = rows[0] if rows and self._single else rows
        return SimpleNamespace(data=data)


class FakeAdmin:
    def __init__(self, responses=None, defaults=None):
        self.responses = responses or {}
        self.defaults = defaults or {}
        self.calls: list[dict] = []

    def table(self, name):
        return FakeQuery(self, name)


@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _patient_user(uid="patient-1"):
    return {
        "id": uid,
        "is_patient": True,
        "roles": [{"category": PATIENT, "organization_id": "org-1"}],
    }


def _practitioner_user(uid="user-prac-1", org="org-1"):
    return {
        "id": uid,
        "is_practitioner": True,
        "roles": [{"category": PRACTITIONER, "organization_id": org}],
        "organization_ids": [org],
    }


def _org_admin_user(uid="admin-1", org="org-1"):
    return {
        "id": uid,
        "is_org_admin": True,
        "roles": [{"category": ORGANIZATION_ADMINISTRATOR, "organization_id": org}],
        "organization_ids": [org],
    }


def _system_admin_user(uid="system-1"):
    return {
        "id": uid,
        "is_admin": True,
        "roles": [{"category": SYSTEM_ADMINISTRATOR, "organization_id": None}],
    }


def _patient_rows(patient_id="patient-1", org="org-1"):
    return {
        _key("patients", id=patient_id): [{"id": patient_id, "organization_id": org}],
        _key("patients", id=PATIENT_UUID): [{"id": PATIENT_UUID, "organization_id": org}],
    }


def _practitioner_rows(practitioner_id="prac-1", user_id="user-prac-1"):
    return {
        _key("practitioners", id=user_id): [],
        _key("practitioners", profile_id=user_id): [
            {"id": practitioner_id, "profile_id": user_id}
        ],
    }


def _care_team_rows(patient_id="patient-1", practitioner_id="prac-1", org="org-1"):
    return {
        _key(
            "patient_care_team",
            patient_id=patient_id,
            practitioner_id=practitioner_id,
            organization_id=org,
            status="active",
        ): [{
            "id": "ct-link-1", "patient_id": patient_id,
            "practitioner_id": practitioner_id, "organization_id": org,
            "status": "active", "start_date": None, "end_date": None,
        }]
    }


def _permission_rows(permission: str, user_id="user-prac-1", org="org-1"):
    return {
        _key("user_roles", user_id=user_id, status="active", organization_id=org): [
            {
                "organization_id": org,
                "roles": {
                    "is_active": True,
                    "role_permissions": [{"permissions": {"name": permission}}],
                },
            }
        ]
    }


def _auth_responses(patient_id="patient-1", org="org-1", practitioner_id="prac-1"):
    responses = _patient_rows(patient_id, org)
    responses.update(_practitioner_rows(practitioner_id))
    responses.update(_care_team_rows(patient_id, practitioner_id, org))
    return responses


def test_mounted_sensitive_routes_match_authorization_map():
    actual = {
        (sorted(route.methods)[0], route.path)
        for route in app.routes
        if getattr(route, "methods", None)
        and any(
            fragment in route.path
            for fragment in (
                "patient",
                "record",
                "encounter",
                "observation",
                "condition",
                "medication",
                "appointment",
                "care-team",
                "consent",
                "lab-result",
                "medical-history",
                "user/summary",
            )
        )
    }
    assert actual == SENSITIVE_ROUTES


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("GET", "/patients/medical-id", None),
        ("GET", "/patients/patient-1/fhir", None),
        ("GET", "/encounters/patient/patient-1", None),
        ("GET", "/observations/encounter/enc-1", None),
        ("GET", "/conditions/patient/patient-1", None),
        ("GET", "/medication-requests/encounter/enc-1", None),
        ("GET", "/appointments/patient/patient-1", None),
        ("GET", "/care-teams/patient/patient-1", None),
        ("GET", "/consents/me", None),
        ("GET", "/api/v1/lab-results/lab-1", None),
        ("GET", "/api/v1/user/summary", None),
        (
            "POST",
            "/encounters/",
            {"patient_id": "patient-1", "organization_id": "org-1", "encounter_class": "outpatient"},
        ),
        (
            "POST",
            "/records/observations",
            {"patient_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "record_type": "observation", "clinical_data": {}},
        ),
    ],
)
def test_sensitive_routes_require_authentication(method, path, body):
    with TestClient(app) as client:
        response = client.request(method, path, json=body)
    assert response.status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "/patients/patient-1/fhir",
        "/encounters/patient/patient-1",
        "/care-teams/patient/patient-1",
    ],
)
def test_sensitive_routes_reject_invalid_token(monkeypatch, path):
    class InvalidTokenError(Exception):
        code = "bad_jwt"

    class InvalidAuth:
        def get_user(self, _token):
            raise InvalidTokenError("synthetic invalid token")

    # Prevent any hosted Auth call while proving fail-closed token validation.
    monkeypatch.setattr(
        "app.core.supabase_client.supabase",
        SimpleNamespace(auth=InvalidAuth()),
    )
    with TestClient(app) as client:
        response = client.get(
            path, headers={"Authorization": "Bearer synthetic-invalid-token"}
        )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "path,module,function_name",
    [
        ("/patients/patient-1/fhir", patients_router, "get_patient_with_records"),
        (f"/patients/{PATIENT_UUID}/summary", patients_router, "get_patient_summary"),
        (f"/patients/{PATIENT_UUID}/timeline", patients_router, "build_patient_timeline"),
        ("/encounters/patient/patient-1", encounter_router, "get_patient_encounters"),
        ("/observations/patient/patient-1", observation_router, "get_patient_observations"),
        ("/conditions/patient/patient-1", condition_router, "get_patient_conditions"),
        ("/medication-requests/patient/patient-1", medication_router, "get_patient_medication"),
        ("/appointments/patient/patient-1", appointment_router, "get_patient_appointments"),
        ("/care-teams/patient/patient-1", care_team_router, "get_patient_care_teams"),
    ],
)
def test_cross_patient_read_denied_before_service(monkeypatch, path, module, function_name):
    monkeypatch.setattr(security, "supabase_admin", FakeAdmin(_patient_rows()))
    called = []
    monkeypatch.setattr(
        module,
        function_name,
        lambda *args, **kwargs: called.append((args, kwargs)) or [],
    )
    with TestClient(app) as client:
        app.dependency_overrides[security.get_current_user] = lambda: _patient_user("patient-2")
        response = client.get(path)
    assert response.status_code in {403, 404}
    assert called == []


@pytest.mark.parametrize(
    "path,module,function_name,user",
    [
        (
            "/encounters/patient/patient-1",
            encounter_router,
            "get_patient_encounters",
            _practitioner_user(org="org-2"),
        ),
        (
            "/care-teams/patient/patient-1",
            care_team_router,
            "get_patient_care_teams",
            _org_admin_user(org="org-2"),
        ),
        (
            "/patients/patient-1/fhir",
            patients_router,
            "get_patient_with_records",
            _system_admin_user(),
        ),
    ],
)
def test_cross_organization_and_system_admin_denied_before_service(
    monkeypatch, path, module, function_name, user
):
    monkeypatch.setattr(security, "supabase_admin", FakeAdmin(_patient_rows()))
    called = []
    monkeypatch.setattr(
        module,
        function_name,
        lambda *args, **kwargs: called.append((args, kwargs)) or [],
    )
    with TestClient(app) as client:
        app.dependency_overrides[security.get_current_user] = lambda: user
        response = client.get(path)
    assert response.status_code in {403, 404}
    assert called == []


@pytest.mark.parametrize(
    "method,path,body,module,function_name",
    [
        (
            "POST",
            "/encounters/",
            {"patient_id": "patient-1", "organization_id": "org-1", "encounter_class": "outpatient"},
            encounter_router,
            "create_encounter",
        ),
        (
            "POST",
            "/observations/",
            {
                "patient_id": "patient-1",
                "encounter_id": "enc-1",
                "organization_id": "org-1",
                "category": "vital-signs",
                "code": "synthetic",
            },
            observation_router,
            "create_observation",
        ),
        (
            "POST",
            "/conditions/",
            {
                "patient_id": "patient-1",
                "encounter_id": "enc-1",
                "organization_id": "org-1",
                "code": "synthetic",
                "clinical_status": "active",
                "verification_status": "confirmed",
            },
            condition_router,
            "create_condition",
        ),
        (
            "POST",
            "/medication-requests/",
            {
                "patient_id": "patient-1",
                "encounter_id": "enc-1",
                "organization_id": "org-1",
                "medication_name": "synthetic",
                "dosage_instruction": "synthetic",
            },
            medication_router,
            "create_medication",
        ),
    ],
)
def test_patient_cannot_create_clinical_record(
    monkeypatch, method, path, body, module, function_name
):
    responses = _patient_rows()
    responses[_key("encounters", id="enc-1")] = [
        {"id": "enc-1", "patient_id": "patient-1", "organization_id": "org-1"}
    ]
    monkeypatch.setattr(security, "supabase_admin", FakeAdmin(responses))
    called = []
    monkeypatch.setattr(
        module,
        function_name,
        lambda *args, **kwargs: called.append((args, kwargs)) or {},
    )
    with TestClient(app) as client:
        app.dependency_overrides[security.get_current_user] = lambda: _patient_user()
        response = client.request(method, path, json=body)
    assert response.status_code == 403
    assert called == []


@pytest.mark.parametrize(
    "path,body,module,function_name",
    [
        (
            "/encounters/",
            {"patient_id": "patient-1", "organization_id": "org-1", "encounter_class": "outpatient", "practitioner_id": "prac-forged"},
            encounter_router,
            "create_encounter",
        ),
        (
            "/observations/",
            {
                "patient_id": "patient-1",
                "encounter_id": "enc-1",
                "organization_id": "org-1",
                "practitioner_id": "prac-forged",
                "category": "vital-signs",
                "code": "synthetic",
            },
            observation_router,
            "create_observation",
        ),
        (
            "/conditions/",
            {
                "patient_id": "patient-1",
                "encounter_id": "enc-1",
                "organization_id": "org-1",
                "practitioner_id": "prac-forged",
                "code": "synthetic",
                "clinical_status": "active",
                "verification_status": "confirmed",
            },
            condition_router,
            "create_condition",
        ),
        (
            "/medication-requests/",
            {
                "patient_id": "patient-1",
                "encounter_id": "enc-1",
                "organization_id": "org-1",
                "practitioner_id": "prac-forged",
                "medication_name": "synthetic",
                "dosage_instruction": "synthetic",
            },
            medication_router,
            "create_medication",
        ),
    ],
)
def test_forged_practitioner_id_denied_before_clinical_write(
    monkeypatch, path, body, module, function_name
):
    responses = _auth_responses()
    responses[_key("encounters", id="enc-1")] = [
        {"id": "enc-1", "patient_id": "patient-1", "organization_id": "org-1"}
    ]
    monkeypatch.setattr(security, "supabase_admin", FakeAdmin(responses))
    called = []
    monkeypatch.setattr(
        module,
        function_name,
        lambda *args, **kwargs: called.append((args, kwargs)) or {},
    )
    with TestClient(app) as client:
        app.dependency_overrides[security.get_current_user] = lambda: _practitioner_user()
        response = client.post(path, json=body)
    assert response.status_code == 403
    assert called == []


def test_omitted_practitioner_id_is_bound_to_actor(monkeypatch):
    responses = _auth_responses()
    monkeypatch.setattr(security, "supabase_admin", FakeAdmin(responses))
    captured = []

    def fake_create(payload, created_by, *, authorized_context):
        captured.append((payload.practitioner_id, created_by, authorized_context))
        return {"id": "enc-1"}

    monkeypatch.setattr(encounter_router, "create_encounter", fake_create)
    with TestClient(app) as client:
        app.dependency_overrides[security.get_current_user] = lambda: _practitioner_user()
        response = client.post(
            "/encounters/",
            json={
                "patient_id": "patient-1",
                "organization_id": "org-1",
                "encounter_class": "outpatient",
            },
        )
    assert response.status_code == 200
    assert len(captured) == 1
    assert captured[0][0] == "prac-1"
    assert captured[0][1] == "user-prac-1"


def test_clinician_patient_list_requires_unambiguous_org(monkeypatch):
    monkeypatch.setattr(security, "supabase_admin", FakeAdmin(_practitioner_rows()))
    called = []
    monkeypatch.setattr(
        patients_router,
        "get_my_patients",
        lambda *args, **kwargs: called.append((args, kwargs)) or [],
    )
    user = {
        "id": "user-prac-1",
        "is_practitioner": True,
        "roles": [
            {"category": PRACTITIONER, "organization_id": "org-1"},
            {"category": PRACTITIONER, "organization_id": "org-2"},
        ],
        "organization_ids": ["org-1", "org-2"],
    }
    with TestClient(app) as client:
        app.dependency_overrides[security.get_current_user] = lambda: user
        response = client.get("/patients/mine")
    assert response.status_code == 403
    assert called == []


def test_clinician_patient_list_uses_trusted_care_team_rows(monkeypatch):
    responses = _practitioner_rows()
    responses[_key(
        "patient_care_team",
        practitioner_id="prac-1",
        organization_id="org-1",
        status="active",
    )] = [{"patient_id": "patient-1"}]
    responses[_key(
        "patients",
        organization_id="org-1",
        id=("patient-1",),
    )] = [{"id": "patient-1", "first_name": "Synthetic"}]
    monkeypatch.setattr(patients_service, "supabase_admin", FakeAdmin(responses))
    monkeypatch.setattr(security, "supabase_admin", FakeAdmin(responses))
    with TestClient(app) as client:
        app.dependency_overrides[security.get_current_user] = lambda: _practitioner_user()
        response = client.get("/patients/mine")
    assert response.status_code == 200
    assert response.json()[0]["id"] == "patient-1"


def test_clinician_patient_list_service_denies_direct_call(monkeypatch):
    admin = FakeAdmin()
    monkeypatch.setattr(patients_service, "supabase_admin", admin)
    with pytest.raises(HTTPException) as exc:
        patients_service.get_my_patients(authorized_context=None)
    assert exc.value.status_code == 403
    assert admin.calls == []


def test_care_team_write_emits_attributable_audit(monkeypatch):
    monkeypatch.setattr(security, "supabase_admin", FakeAdmin(_patient_rows()))
    context = clinical.authorize_clinical_access(
        _org_admin_user(),
        resource=clinical.CARE_TEAM,
        action="create",
        patient_id="patient-1",
        organization_id="org-1",
        verified_conditions={"audit_recorded"},
        allow_organization_admin=True,
        organization_care_authority=True,
    )
    context = {**context, "authorized_user_id": "admin-1"}
    audited = []
    import app.core.audit.service as audit_service

    monkeypatch.setattr(audit_service, "log_audit_event", lambda **kwargs: audited.append(kwargs))
    monkeypatch.setattr(
        care_team_service,
        "supabase_admin",
        FakeAdmin(defaults={"care_teams": [{"id": "ct-1"}]}),
    )
    payload = SimpleNamespace(
        patient_id="patient-1",
        organization_id="org-1",
        name=None,
        status="active",
        category=None,
        reason=None,
        managing_organization_id=None,
        notes=None,
    )
    result = care_team_service.create_care_team(payload, authorized_context=context)
    assert result["id"] == "ct-1"
    assert audited
    assert audited[-1]["action"] == "care_team.create"
    assert audited[-1]["resource_type"] == "care_team"
    assert audited[-1]["metadata"]["patient_id"] == "patient-1"
    assert audited[-1]["metadata"]["organization_id"] == "org-1"


def test_clinical_display_services_do_not_overfetch_rows():
    root = Path(__file__).resolve().parents[2] / "app" / "modules"
    service_files = [
        "patients/service.py",
        "records/service.py",
        "encounters/service.py",
        "observations/service.py",
        "conditions/service.py",
        "medications/service.py",
        "appointments/service.py",
        "care_team/service.py",
        "consents/service.py",
        "laboratory/service.py",
        "prescriptions/service.py",
        "reminders/service.py",
    ]
    for relative in service_files:
        source = (root / relative).read_text(encoding="utf-8")
        assert not re.search(r'\.select\(\s*"\*"\s*\)', source), relative
        assert not re.search(r'\.select\(\s*f?"""\s*\*', source), relative


def test_lab_and_reminder_projections_match_local_schema():
    assert "result_data" in lab_service.LAB_DETAIL_SELECT
    assert "raw" not in lab_service.LAB_DETAIL_SELECT
    reminder_source = (
        Path(__file__).resolve().parents[2]
        / "app/modules/reminders/service.py"
    ).read_text(encoding="utf-8")
    assert "reminder_date" in reminder_source
    assert "scheduled_at" not in reminder_source
