from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.modules.consents import service
from app.modules.consents.schemas import ConsentGrant


class _Query:
    def __init__(self, table, state):
        self.table = table
        self.state = state

    def insert(self, payload):
        self.state["insert"] = payload
        return self

    def update(self, payload):
        self.state["update"] = payload
        return self

    def select(self, *args, **kwargs):
        return self

    def eq(self, key, value):
        self.state.setdefault("filters", []).append((key, value))
        return self

    def limit(self, value):
        return self

    def execute(self):
        return type("Result", (), {"data": [{"id": "consent-1"}]})()


class _Client:
    def __init__(self, existing=None):
        self.state = {}
        self.existing = existing if existing is not None else [{"id": "consent-1"}]

    def table(self, name):
        query = _Query(name, self.state)
        if self.existing and name == "consent_records" and not self.state.get("insert"):
            original_execute = query.execute

            def execute():
                if query.table == "consent_records" and "update" in self.state:
                    return type("Result", (), {"data": [{"id": "consent-1"}]})()
                return original_execute()

            query.execute = execute
        return query


def _payload(**overrides):
    now = datetime.now(timezone.utc)
    data = {
        "organization_id": "org-1",
        "practitioner_id": "prac-1",
        "consent_type": "treatment",
        "access_level": "read",
        "expires_at": now + timedelta(days=1),
    }
    data.update(overrides)
    return ConsentGrant(**data)


def test_grant_consent_records_trusted_provenance(monkeypatch):
    client = _Client()
    monkeypatch.setattr(service, "supabase_admin", client)

    result = service.grant_consent(
        "patient-1", _payload(), actor_user_id="patient-1"
    )

    assert result == {"id": "consent-1"}
    inserted = client.state["insert"]
    assert inserted["patient_id"] == "patient-1"
    assert inserted["granted_by"] == "patient-1"
    assert inserted["granted_at"]
    assert inserted["effective_from"]
    assert inserted["expires_at"]
    assert inserted["emergency_access"] is False
    assert inserted["status"] == "active"


def test_revoke_consent_records_trusted_revoker(monkeypatch):
    existing = [{"id": "consent-1", "patient_id": "patient-1"}]
    client = _Client(existing=existing)
    monkeypatch.setattr(service, "supabase_admin", client)

    payload = type("Revoke", (), {"consent_id": "consent-1", "revoked_reason": None})()
    result = service.revoke_consent("patient-1", payload, actor_user_id="patient-1")

    assert result == {"id": "consent-1"}
    assert client.state["update"]["revoked_by"] == "patient-1"
    assert client.state["update"]["revoked_at"]
    assert client.state["update"]["status"] == "revoked"
    assert ("patient_id", "patient-1") in client.state["filters"]


def test_consent_schema_requires_finite_expiry_and_blocks_emergency():
    with pytest.raises(ValidationError):
        ConsentGrant(
            organization_id="org-1",
            consent_type="treatment",
            access_level="read",
        )
    with pytest.raises(ValidationError):
        _payload(emergency_access=True)


def test_grant_consent_denies_expired_or_emergency_payload(monkeypatch):
    client = _Client()
    monkeypatch.setattr(service, "supabase_admin", client)

    with pytest.raises(HTTPException) as exc:
        service.grant_consent(
            "patient-1",
            type(
                "Payload",
                (),
                {
                    "organization_id": "org-1",
                    "practitioner_id": "prac-1",
                    "consent_type": "treatment",
                    "access_level": "read",
                    "purpose_of_use": None,
                    "legal_basis": None,
                    "emergency_access": True,
                    "effective_from": None,
                    "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
                    "metadata": None,
                },
            )(),
            actor_user_id="patient-1",
        )
    assert exc.value.status_code == 400
    assert "insert" not in client.state


def test_grant_consent_denies_expired_payload(monkeypatch):
    client = _Client()
    monkeypatch.setattr(service, "supabase_admin", client)

    with pytest.raises(HTTPException) as exc:
        service.grant_consent(
            "patient-1",
            type(
                "Payload",
                (),
                {
                    "organization_id": "org-1",
                    "practitioner_id": "prac-1",
                    "consent_type": "treatment",
                    "access_level": "read",
                    "purpose_of_use": None,
                    "legal_basis": None,
                    "emergency_access": False,
                    "effective_from": None,
                    "expires_at": datetime.now(timezone.utc) - timedelta(days=1),
                    "metadata": None,
                },
            )(),
            actor_user_id="patient-1",
        )
    assert exc.value.status_code == 400
    assert "insert" not in client.state
