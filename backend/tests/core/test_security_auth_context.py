from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core import security
from app.core.role_catalogue import (
    ORGANIZATION_ADMINISTRATOR,
    PATIENT,
    PRACTITIONER,
    SYSTEM_ADMINISTRATOR,
)


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.filters = []

    def select(self, columns):
        self.columns = columns
        return self

    def eq(self, key, value):
        self.filters.append(("eq", key, value))
        return self

    def in_(self, key, values):
        self.filters.append(("in", key, tuple(sorted(str(value) for value in values))))
        return self

    def execute(self):
        self.client.calls.append((self.table, self.columns, list(self.filters)))
        if self.table == "user_roles":
            return SimpleNamespace(data=self.client.role_rows)
        if self.table == "roles":
            return SimpleNamespace(data=self.client.role_rows_by_id)
        raise AssertionError(f"Unexpected table: {self.table}")


class FakeSupabaseAdmin:
    def __init__(self, role_rows, role_rows_by_id):
        self.role_rows = role_rows
        self.role_rows_by_id = role_rows_by_id
        self.calls = []

    def table(self, name):
        return FakeQuery(self, name)


class FakeAuthError(Exception):
    def __init__(self, code, status_code):
        super().__init__("provider error")
        self.code = code
        self.status_code = status_code


def credentials():
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-test-token")


def install_auth(monkeypatch, *, user=None, error=None):
    from app.core import supabase_client

    def get_user(token):
        assert token == "valid-test-token"
        if error:
            raise error
        return SimpleNamespace(user=user or SimpleNamespace(id="user-1", email="user@example.test"))

    fake_client = SimpleNamespace(auth=SimpleNamespace(get_user=get_user))
    monkeypatch.setattr(supabase_client, "supabase", fake_client)


def role_assignment(role_id, organization_id=None, status="active"):
    return {
        "role_id": role_id,
        "organization_id": organization_id,
        "status": status,
    }


def role(role_id, name, role_type, organization_id=None, is_active=True):
    return {
        "id": role_id,
        "name": name,
        "role_type": role_type,
        "organization_id": organization_id,
        "is_active": is_active,
    }


def install_roles(monkeypatch, assignments, definitions):
    fake_admin = FakeSupabaseAdmin(assignments, definitions)
    monkeypatch.setattr(security, "supabase_admin", fake_admin)
    return fake_admin


def test_get_current_user_resolves_all_valid_active_assignments(monkeypatch):
    install_auth(monkeypatch)
    fake_admin = install_roles(
        monkeypatch,
        [
            role_assignment("patient-role"),
            role_assignment("practitioner-a", "org-a"),
            role_assignment("practitioner-b", "org-b"),
        ],
        [
            role("patient-role", "patient", "system"),
            role("practitioner-a", "practitioner", "organization", "org-a"),
            role("practitioner-b", "nurse", "organization", "org-b"),
        ],
    )

    result = security.get_current_user(credentials())

    assert result["id"] == "user-1"
    assert result["email"] == "user@example.test"
    assert {item["category"] for item in result["roles"]} == {PATIENT, PRACTITIONER}
    assert result["organization_ids"] == ["org-a", "org-b"]
    assert result["is_patient"] is True
    assert result["is_practitioner"] is True
    assert result["role"] is None
    assert fake_admin.calls[0][2] == [
        ("eq", "user_id", "user-1"),
        ("eq", "status", "active"),
    ]


def test_get_current_user_preserves_unmapped_but_requires_a_recognized_role(monkeypatch):
    install_auth(monkeypatch)
    install_roles(
        monkeypatch,
        [
            role_assignment("valid-practitioner", "org-a"),
            role_assignment("legacy-admin", "org-b"),
        ],
        [
            role("valid-practitioner", "practitioner", "organization", "org-a"),
            role("legacy-admin", "admin", "organization", "org-b"),
        ],
    )

    result = security.get_current_user(credentials())

    assert [item["category"] for item in result["roles"]] == [PRACTITIONER, "unmapped"]
    assert result["organization_ids"] == ["org-a"]


def test_get_current_user_denies_all_unmapped_assignments(monkeypatch):
    install_auth(monkeypatch)
    install_roles(
        monkeypatch,
        [role_assignment("legacy-admin", "org-a")],
        [role("legacy-admin", "admin", "organization", "org-a")],
    )

    with pytest.raises(HTTPException) as exc:
        security.get_current_user(credentials())

    assert exc.value.status_code == 403


def test_get_current_user_denies_inactive_role_definition(monkeypatch):
    install_auth(monkeypatch)
    install_roles(
        monkeypatch,
        [role_assignment("inactive-role", "org-a")],
        [role("inactive-role", "org_admin", "organization", "org-a", is_active=False)],
    )

    with pytest.raises(HTTPException) as exc:
        security.get_current_user(credentials())

    assert exc.value.status_code == 403


def test_get_current_user_denies_when_role_definition_is_missing(monkeypatch):
    install_auth(monkeypatch)
    install_roles(monkeypatch, [role_assignment("missing-role", "org-a")], [])

    with pytest.raises(HTTPException) as exc:
        security.get_current_user(credentials())

    assert exc.value.status_code == 403


def test_get_current_user_returns_401_for_invalid_jwt(monkeypatch):
    install_auth(
        monkeypatch,
        error=FakeAuthError("bad_jwt", 401),
    )

    with pytest.raises(HTTPException) as exc:
        security.get_current_user(credentials())

    assert exc.value.status_code == 401


def test_get_current_user_returns_503_for_auth_infrastructure_error(monkeypatch):
    install_auth(
        monkeypatch,
        error=FakeAuthError("unexpected_failure", 500),
    )

    with pytest.raises(HTTPException) as exc:
        security.get_current_user(credentials())

    assert exc.value.status_code == 503


def test_get_current_user_returns_503_when_role_resolution_fails(monkeypatch):
    install_auth(monkeypatch)

    class BrokenAdmin:
        def table(self, name):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(security, "supabase_admin", BrokenAdmin())

    with pytest.raises(HTTPException) as exc:
        security.get_current_user(credentials())

    assert exc.value.status_code == 503


def test_get_current_user_returns_401_when_auth_returns_no_user(monkeypatch):
    install_auth(monkeypatch, user=None)
    from app.core import supabase_client
    monkeypatch.setattr(
        supabase_client,
        "supabase",
        SimpleNamespace(auth=SimpleNamespace(get_user=lambda token: SimpleNamespace(user=None))),
    )

    with pytest.raises(HTTPException) as exc:
        security.get_current_user(credentials())

    assert exc.value.status_code == 401
