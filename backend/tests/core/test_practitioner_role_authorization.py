from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import HTTPException

from app.core.audit import service as audit_service
from app.modules.practitioner_roles import service as practitioner_roles

ORG_ID = "11111111-1111-4111-8111-111111111111"
OTHER_ORG_ID = "22222222-2222-4222-8222-222222222222"
ACTOR_ID = "33333333-3333-4333-8333-333333333333"
TARGET_ID = "44444444-4444-4444-8444-444444444444"
ROLE_ID = "55555555-5555-4555-8555-555555555555"


def org_admin_roles(organization_id: str = ORG_ID) -> list[dict]:
    return [{
        "name": "org_admin",
        "role_type": "organization",
        "organization_id": organization_id,
        "category": "organization_administrator",
    }]


@dataclass
class Call:
    table: str
    operation: str
    payload: dict | None
    filters: dict
    columns: str | None = None


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, fake: FakeSupabaseAdmin, table: str):
        self.fake = fake
        self.table = table
        self.operation = ""
        self.payload = None
        self.filters: dict = {}
        self.columns = None

    def select(self, columns):
        self.operation = "select"
        self.columns = columns
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
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
        self.fake.calls.append(
            Call(self.table, self.operation, self.payload, dict(self.filters), self.columns)
        )
        key = (self.table, self.operation)
        result = self.fake.results.get(key)
        if callable(result):
            result = result(self.filters, self.payload)
        return FakeResult(result)


class FakeSupabaseAdmin:
    def __init__(self, *, role_row=None, existing_role=False):
        self.calls: list[Call] = []
        self.results = {
            ("audit_logs", "insert"): [{"id": "audit-1"}],
            ("practitioners", "select"): [{"id": TARGET_ID}],
            ("practitioner_roles", "select"): role_row or [],
            ("practitioner_roles", "insert"): [{"id": ROLE_ID}],
            ("practitioner_roles", "update"): [{"id": ROLE_ID}],
        }
        if existing_role:
            self.results[("practitioner_roles", "select")] = [{"id": ROLE_ID}]

    def table(self, name):
        return FakeQuery(self, name)


class AssignPayload:
    organization_id = ORG_ID
    role_code = "doctor"
    specialty_code = "cardiology"
    department = "cardiology"
    permissions = {"can_prescribe": True}
    start_date = None
    end_date = None


class UpdatePayload:
    model_fields_set = {"permissions", "active"}

    def model_dump(self, *, exclude_unset=False):
        return {"permissions": {"can_prescribe": False}, "active": False}


def patch_clients(monkeypatch, fake):
    # The audit helper owns its own client reference; patch both clients so
    # tests never reach the configured (hosted) Supabase URL.
    monkeypatch.setattr(practitioner_roles, "supabase_admin", fake)
    monkeypatch.setattr(audit_service, "supabase_admin", fake)


def call_assign(fake, *, actor_roles, target_id=TARGET_ID):
    return practitioner_roles.assign_practitioner_role(
        actor_id=ACTOR_ID,
        actor_roles=actor_roles,
        target_practitioner_id=target_id,
        payload=AssignPayload(),
    )


def test_assign_denied_without_org_admin(monkeypatch):
    fake = FakeSupabaseAdmin()
    patch_clients(monkeypatch, fake)

    with pytest.raises(HTTPException) as exc:
        call_assign(fake, actor_roles=[])

    assert exc.value.status_code == 403
    assert fake.calls == []  # policy runs before any privileged call


def test_assign_denied_for_other_organization(monkeypatch):
    fake = FakeSupabaseAdmin()
    patch_clients(monkeypatch, fake)

    with pytest.raises(HTTPException) as exc:
        call_assign(fake, actor_roles=org_admin_roles(OTHER_ORG_ID))

    assert exc.value.status_code == 403
    assert fake.calls == []


def test_assign_denies_self_grant(monkeypatch):
    fake = FakeSupabaseAdmin()
    patch_clients(monkeypatch, fake)

    with pytest.raises(HTTPException) as exc:
        call_assign(fake, actor_roles=org_admin_roles(), target_id=ACTOR_ID)

    assert exc.value.status_code == 403
    assert fake.calls == []


def test_assign_audits_before_write_and_scopes_resource(monkeypatch):
    fake = FakeSupabaseAdmin()
    patch_clients(monkeypatch, fake)

    result = call_assign(fake, actor_roles=org_admin_roles())

    assert result == {"id": ROLE_ID}
    assert [call.table for call in fake.calls] == [
        "practitioners", "practitioner_roles", "audit_logs", "practitioner_roles"
    ]
    audit = fake.calls[2]
    assert audit.payload["actor_id"] == ACTOR_ID
    assert audit.payload["resource_id"] == TARGET_ID
    assert audit.payload["metadata"] == {
        "role_code": "doctor",
        "organization_id": ORG_ID,
    }
    insert = fake.calls[3]
    assert insert.operation == "insert"
    assert insert.payload["practitioner_id"] == TARGET_ID
    assert insert.payload["organization_id"] == ORG_ID


def test_assign_audit_failure_blocks_write(monkeypatch):
    fake = FakeSupabaseAdmin()
    patch_clients(monkeypatch, fake)

    def fail_audit(**_):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(practitioner_roles, "log_audit_event", fail_audit)

    with pytest.raises(RuntimeError):
        call_assign(fake, actor_roles=org_admin_roles())

    assert not any(
        call.table == "practitioner_roles" and call.operation == "insert"
        for call in fake.calls
    )


def test_update_requires_admin_for_target_role_organization(monkeypatch):
    fake = FakeSupabaseAdmin(role_row=[{
        "id": ROLE_ID,
        "organization_id": ORG_ID,
        "practitioner_id": TARGET_ID,
        "role_code": "doctor",
    }])
    patch_clients(monkeypatch, fake)

    with pytest.raises(HTTPException) as exc:
        practitioner_roles.update_practitioner_role(
            actor_id=ACTOR_ID,
            actor_roles=org_admin_roles(OTHER_ORG_ID),
            role_id=ROLE_ID,
            payload=UpdatePayload(),
        )

    assert exc.value.status_code == 403
    assert not any(call.operation == "update" for call in fake.calls)


def test_update_is_constrained_to_authorized_organization(monkeypatch):
    fake = FakeSupabaseAdmin(role_row=[{
        "id": ROLE_ID,
        "organization_id": ORG_ID,
        "practitioner_id": TARGET_ID,
        "role_code": "doctor",
    }])
    patch_clients(monkeypatch, fake)

    practitioner_roles.update_practitioner_role(
        actor_id=ACTOR_ID,
        actor_roles=org_admin_roles(),
        role_id=ROLE_ID,
        payload=UpdatePayload(),
    )

    update = next(
        call for call in fake.calls
        if call.table == "practitioner_roles" and call.operation == "update"
    )
    assert update.filters == {"id": ROLE_ID, "organization_id": ORG_ID}
    audit = next(call for call in fake.calls if call.table == "audit_logs")
    assert audit.payload["metadata"] == {
        "organization_id": ORG_ID,
        "updated_fields": ["active", "permissions"],
    }


def test_organization_listing_requires_org_admin_before_query(monkeypatch):
    fake = FakeSupabaseAdmin()
    patch_clients(monkeypatch, fake)

    with pytest.raises(HTTPException) as exc:
        practitioner_roles.get_organization_practitioners(
            actor_roles=[], organization_id=ORG_ID
        )

    assert exc.value.status_code == 403
    assert fake.calls == []


def test_organization_listing_omits_contact_data(monkeypatch):
    fake = FakeSupabaseAdmin()
    patch_clients(monkeypatch, fake)

    practitioner_roles.get_organization_practitioners(
        actor_roles=org_admin_roles(), organization_id=ORG_ID
    )

    call = fake.calls[0]
    assert call.columns is not None
    assert "email" not in call.columns
    assert "phone" not in call.columns
