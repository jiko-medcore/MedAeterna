from __future__ import annotations

from types import SimpleNamespace

from app.core.audit import service as audit_service


class FakeInsert:
    def __init__(self, captured: list[dict]):
        self.captured = captured
        self.payload: dict | None = None

    def insert(self, payload: dict):
        self.payload = payload
        return self

    def execute(self):
        self.captured.append(self.payload)
        return SimpleNamespace(data=[self.payload])


class FakeSupabaseAdmin:
    def __init__(self):
        self.calls: list[dict] = []
        self.insert = FakeInsert(self.calls)

    def table(self, name: str):
        assert name == "audit_logs"
        return self.insert


def test_log_audit_event_accepts_organization_scope(monkeypatch):
    fake = FakeSupabaseAdmin()
    monkeypatch.setattr(audit_service, "supabase_admin", fake)
    metadata = {"updated_fields": ["primary_color"]}

    audit_service.log_audit_event(
        actor_id="actor-1",
        actor_type="user",
        action="organization.branding.updated",
        resource_type="organization_branding",
        resource_id="org-1",
        organization_id="org-1",
        metadata=metadata,
    )

    assert fake.calls == [{
        "actor_id": "actor-1",
        "actor_type": "user",
        "action": "organization.branding.updated",
        "resource_type": "organization_branding",
        "resource_id": "org-1",
        "metadata": {
            "updated_fields": ["primary_color"],
            "organization_id": "org-1",
        },
    }]
    assert metadata == {"updated_fields": ["primary_color"]}


def test_log_audit_event_without_organization_scope(monkeypatch):
    fake = FakeSupabaseAdmin()
    monkeypatch.setattr(audit_service, "supabase_admin", fake)

    audit_service.log_audit_event(
        actor_id=None,
        actor_type="system",
        action="EVENT_DEAD_LETTERED",
        resource_type="event",
        resource_id="event-1",
    )

    assert fake.calls[0]["metadata"] == {}
