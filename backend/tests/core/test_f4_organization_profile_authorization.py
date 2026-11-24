from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.modules.organizations.profile import router as profile_router
from app.modules.organizations.profile import service as profile_service
from app.modules.organizations.profile.schemas import OrganizationProfileUpdate

ORG_ID = "11111111-1111-4111-8111-111111111111"
OTHER_ORG_ID = "22222222-2222-4222-8222-222222222222"
ACTOR_ID = "33333333-3333-4333-8333-333333333333"


def org_admin_roles(organization_id: str = ORG_ID) -> list[dict]:
    return [{
        "name": "org_admin",
        "role_type": "organization",
        "organization_id": organization_id,
        "category": "organization_administrator",
    }]


def profile_payload() -> OrganizationProfileUpdate:
    return OrganizationProfileUpdate(name="Updated Hospital")


def organization_row() -> dict:
    return {
        "id": ORG_ID,
        "name": "MedCore",
        "active": True,
        "type": "Hospital",
    }


def test_update_denies_non_admin_before_any_privileged_call(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        profile_service,
        "get_organization_profile",
        lambda _: calls.append("query") or organization_row(),
    )
    monkeypatch.setattr(
        profile_service,
        "update_organization_profile",
        lambda *_: calls.append("write") or organization_row(),
    )
    monkeypatch.setattr(
        profile_service,
        "log_audit_event",
        lambda **_: calls.append("audit"),
    )

    with pytest.raises(HTTPException) as exc:
        profile_service.update_profile(
            organization_id=ORG_ID,
            payload=profile_payload(),
            actor_id=ACTOR_ID,
            actor_roles=[],
        )

    assert exc.value.status_code == 403
    assert calls == []


def test_update_denies_admin_for_a_different_organization(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        profile_service,
        "get_organization_profile",
        lambda _: calls.append("query") or organization_row(),
    )

    with pytest.raises(HTTPException) as exc:
        profile_service.update_profile(
            organization_id=ORG_ID,
            payload=profile_payload(),
            actor_id=ACTOR_ID,
            actor_roles=org_admin_roles(OTHER_ORG_ID),
        )

    assert exc.value.status_code == 403
    assert calls == []


def test_update_audits_before_write_and_scopes_audit(monkeypatch):
    calls: list[str] = []
    audit_kwargs: dict = {}
    monkeypatch.setattr(
        profile_service,
        "get_organization_profile",
        lambda _: calls.append("query") or organization_row(),
    )
    monkeypatch.setattr(
        profile_service,
        "update_organization_profile",
        lambda *_: calls.append("write") or organization_row(),
    )

    def fake_audit(**kwargs):
        calls.append("audit")
        audit_kwargs.update(kwargs)

    monkeypatch.setattr(profile_service, "log_audit_event", fake_audit)

    profile_service.update_profile(
        organization_id=ORG_ID,
        payload=profile_payload(),
        actor_id=ACTOR_ID,
        actor_roles=org_admin_roles(),
    )

    assert calls == ["query", "audit", "write"]
    assert audit_kwargs["resource_id"] == ORG_ID
    assert audit_kwargs["metadata"]["organization_id"] == ORG_ID
    assert "name" in audit_kwargs["metadata"]["updated_fields"]


def test_router_resolves_organization_from_trusted_admin_roles(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        profile_router,
        "update_profile",
        lambda **kwargs: captured.update(kwargs) or organization_row(),
    )

    profile_router.update_organization_profile(
        payload=profile_payload(),
        current_user={"id": ACTOR_ID, "roles": org_admin_roles()},
    )

    assert captured["organization_id"] == ORG_ID
    assert captured["actor_id"] == ACTOR_ID
    assert captured["actor_roles"] == org_admin_roles()


def test_router_fails_closed_for_multi_organization_admin(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        profile_router,
        "update_profile",
        lambda **kwargs: captured.update(kwargs) or organization_row(),
    )

    with pytest.raises(HTTPException) as exc:
        profile_router.update_organization_profile(
            payload=profile_payload(),
            current_user={
                "id": ACTOR_ID,
                "roles": org_admin_roles() + org_admin_roles(OTHER_ORG_ID),
            },
        )

    assert exc.value.status_code == 403
    assert captured == {}
