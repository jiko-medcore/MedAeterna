from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core import security
from app.core.role_catalogue import ORGANIZATION_ADMINISTRATOR, PATIENT, PRACTITIONER, SYSTEM_ADMINISTRATOR


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.filters = []
        self._limit = None

    def select(self, *args, **kwargs):
        return self

    def eq(self, key, value):
        self.filters.append(("eq", key, value))
        return self

    def is_(self, key, value):
        self.filters.append(("is", key, value))
        return self

    def in_(self, key, values):
        self.filters.append(("in", key, tuple(sorted(str(v) for v in values))))
        return self

    def limit(self, n):
        self._limit = n
        return self

    def maybe_single(self):
        self._single = "maybe"
        return self

    def single(self):
        self._single = "single"
        return self

    def execute(self):
        key = (self.table, tuple(sorted(self.filters)))
        rows = self.client.responses.get(key)
        if rows is None:
            rows = self.client.responses.get((self.table, tuple(self.filters)), [])
        if getattr(self, "_single", None):
            data = rows[0] if rows else None
            return SimpleNamespace(data=data)
        return SimpleNamespace(data=rows)


class FakeSupabaseAdmin:
    def __init__(self, responses):
        self.responses = responses

    def table(self, name):
        return FakeQuery(self, name)


def _patient_user(uid="patient-1", org=None):
    return {"id": uid, "roles": [{"category": PATIENT, "organization_id": None}]}


def _practitioner_user(uid="user-prac-1", org="org-1"):
    return {
        "id": uid,
        "roles": [{"category": PRACTITIONER, "organization_id": org}],
        "organization_ids": [org],
    }


def _system_admin(uid="admin-1"):
    return {"id": uid, "roles": [{"category": SYSTEM_ADMINISTRATOR, "organization_id": None}]}


def test_authorize_patient_access_allows_patient_self(monkeypatch):
    responses = {
        ("patients", (("eq", "id", "patient-1"),)): [{"id": "patient-1", "organization_id": "org-1"}],
    }
    monkeypatch.setattr(security, "supabase_admin", FakeSupabaseAdmin(responses))
    result = security.authorize_patient_access(_patient_user(), "patient-1")
    assert result["authorized_patient_id"] == "patient-1"


def test_authorize_patient_access_denies_cross_org_patient(monkeypatch):
    responses = {
        ("patients", (("eq", "id", "patient-1"),)): [{"id": "patient-1", "organization_id": "org-1"}],
    }
    monkeypatch.setattr(security, "supabase_admin", FakeSupabaseAdmin(responses))
    with pytest.raises(HTTPException) as exc:
        security.authorize_patient_access(_practitioner_user(), "patient-1", organization_id="org-2")
    assert exc.value.status_code == 404


def test_authorize_patient_access_requires_verified_relationship(monkeypatch):
    responses = {
        ("patients", (("eq", "id", "patient-1"),)): [{"id": "patient-1", "organization_id": "org-1"}],
        ("practitioners", (("eq", "id", "user-prac-1"),)): [],
        ("practitioners", (("eq", "profile_id", "user-prac-1"),)): [{"id": "prac-1", "profile_id": "user-prac-1"}],
        ("patient_care_team", (("eq", "organization_id", "org-1"), ("eq", "patient_id", "patient-1"), ("eq", "practitioner_id", "prac-1"), ("eq", "status", "active"))): [],
        ("consent_records", (("eq", "organization_id", "org-1"), ("eq", "patient_id", "patient-1"), ("eq", "status", "active"))): [],
        ("clinicians_patients", (("eq", "active", True), ("eq", "clinician_id", "user-prac-1"), ("eq", "patient_id", "patient-1"))): [],
    }
    monkeypatch.setattr(security, "supabase_admin", FakeSupabaseAdmin(responses))
    with pytest.raises(HTTPException) as exc:
        security.authorize_patient_access(_practitioner_user(), "patient-1", organization_id="org-1")
    assert exc.value.status_code == 403


def test_authorize_patient_access_allows_active_care_team(monkeypatch):
    responses = {
        ("patients", (("eq", "id", "patient-1"),)): [{"id": "patient-1", "organization_id": "org-1"}],
        ("practitioners", (("eq", "id", "user-prac-1"),)): [],
        ("practitioners", (("eq", "profile_id", "user-prac-1"),)): [{"id": "prac-1", "profile_id": "user-prac-1"}],
        ("patient_care_team", (("eq", "organization_id", "org-1"), ("eq", "patient_id", "patient-1"), ("eq", "practitioner_id", "prac-1"), ("eq", "status", "active"))): [{"id": "ct-1"}],
    }
    monkeypatch.setattr(security, "supabase_admin", FakeSupabaseAdmin(responses))
    result = security.authorize_patient_access(_practitioner_user(), "patient-1", organization_id="org-1")
    assert result["authorized_practitioner_id"] == "prac-1"


def test_authorize_patient_access_denies_system_admin_without_patient_scope(monkeypatch):
    responses = {
        ("patients", (("eq", "id", "patient-1"),)): [{"id": "patient-1", "organization_id": "org-1"}],
    }
    monkeypatch.setattr(security, "supabase_admin", FakeSupabaseAdmin(responses))
    with pytest.raises(HTTPException) as exc:
        security.authorize_patient_access(_system_admin(), "patient-1")
    assert exc.value.status_code == 403


def test_get_user_permissions_filters_by_organization(monkeypatch):
    responses = {
        (
            "user_roles",
            (
                ("eq", "organization_id", "org-1"),
                ("eq", "status", "active"),
                ("eq", "user_id", "user-1"),
            ),
        ): [
            {
                "organization_id": "org-1",
                "status": "active",
                "roles": {
                    "is_active": True,
                    "role_permissions": [{"permissions": {"name": "manage_organization"}}],
                },
            }
        ]
    }
    monkeypatch.setattr(security, "supabase_admin", FakeSupabaseAdmin(responses))
    perms = security.get_user_permissions("user-1", organization_id="org-1")
    assert perms == {"manage_organization"}


def test_authorize_permission_requires_explicit_org_and_permission(monkeypatch):
    monkeypatch.setattr(security, "get_user_permissions", lambda user_id, organization_id=None: {"view"})
    with pytest.raises(HTTPException) as missing_org:
        security.authorize_permission({"id": "u1"}, "manage_organization", "")
    assert missing_org.value.status_code == 400
    with pytest.raises(HTTPException) as denied:
        security.authorize_permission({"id": "u1"}, "manage_organization", "org-1")
    assert denied.value.status_code == 403


def test_require_permission_fails_closed_without_derivable_context(monkeypatch):
    monkeypatch.setattr(security, "get_user_permissions", lambda user_id, organization_id=None: set())

    class Req:
        path_params = {}
        query_params = {}
        url = SimpleNamespace(path="/records/observations")

    dep = security.require_permission("create_observation")
    with pytest.raises(HTTPException) as exc:
        dep(Req(), {"id": "u1", "organization_ids": [], "roles": []})
    assert exc.value.status_code == 400


def test_require_patient_access_manual_compatibility_builds_context(monkeypatch):
    responses = {
        ("user_roles", (("eq", "status", "active"), ("eq", "user_id", "user-prac-1"))): [
            {"organization_id": "org-1", "role_id": "role-1", "status": "active"}
        ],
        ("roles", (("in", "id", ("role-1",)),)): [
            {"id": "role-1", "name": "practitioner", "role_type": "organization", "organization_id": "org-1", "is_active": True}
        ],
        ("patients", (("eq", "id", "patient-1"),)): [{"id": "patient-1", "organization_id": "org-1"}],
        ("practitioners", (("eq", "id", "user-prac-1"),)): [],
        ("practitioners", (("eq", "profile_id", "user-prac-1"),)): [{"id": "prac-1", "profile_id": "user-prac-1"}],
        ("patient_care_team", (("eq", "organization_id", "org-1"), ("eq", "patient_id", "patient-1"), ("eq", "practitioner_id", "prac-1"), ("eq", "status", "active"))): [{"id": "ct-1"}],
    }
    monkeypatch.setattr(security, "supabase_admin", FakeSupabaseAdmin(responses))
    assert security.require_patient_access_manual("patient-1", "user-prac-1") is True


def _consent_responses(rows):
    return {
        (
            "consent_records",
            (
                ("eq", "organization_id", "org-1"),
                ("eq", "patient_id", "patient-1"),
                ("eq", "status", "active"),
            ),
        ): rows
    }


def _valid_consent_row(**overrides):
    now = datetime.now(timezone.utc)
    row = {
        "id": "consent-1",
        "granted_by": "patient-1",
        "granted_at": (now - timedelta(days=1)).isoformat(),
        "effective_from": (now - timedelta(days=1)).isoformat(),
        "expires_at": (now + timedelta(days=1)).isoformat(),
        "revoked_at": None,
        "emergency_access": False,
        "consent_type": "treatment",
        "practitioner_id": "prac-1",
        "organization_id": "org-1",
    }
    row.update(overrides)
    return row


def test_active_consent_requires_finite_expiry_and_grant_provenance(monkeypatch):
    monkeypatch.setattr(
        security,
        "supabase_admin",
        FakeSupabaseAdmin(_consent_responses([_valid_consent_row()])),
    )
    assert security._active_consent_access("patient-1", "prac-1", "org-1") is True


@pytest.mark.parametrize(
    "overrides",
    [
        {"expires_at": None},
        {"granted_by": None},
        {"granted_at": None},
        {"revoked_at": "2026-11-21T00:00:00+00:00"},
        {"emergency_access": True},
        {"consent_type": "emergency"},
        {"expires_at": "2020-01-01T00:00:00+00:00"},
    ],
)
def test_active_consent_denies_unproven_or_non_finite_rows(monkeypatch, overrides):
    monkeypatch.setattr(
        security,
        "supabase_admin",
        FakeSupabaseAdmin(_consent_responses([_valid_consent_row(**overrides)])),
    )
    assert security._active_consent_access("patient-1", "prac-1", "org-1") is False
