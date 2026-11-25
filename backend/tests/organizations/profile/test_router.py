import pytest
from fastapi import HTTPException

from main import app
from app.modules.organizations.dependencies import require_current_user_organization_admin
from tests.factories.constants import ORGANIZATION_ID
from tests.factories.user import USER_ID


def test_get_profile_authenticated(
    authenticated_client,
    organization_profile_data,
    mocker,
):
    mock_get_profile = mocker.patch(
        "app.modules.organizations.profile.router.get_profile",
        return_value=organization_profile_data,
    )

    response = authenticated_client.get("/organizations/profile")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(organization_profile_data["id"])
    assert body["name"] == "Test Hospital"
    mock_get_profile.assert_called_once_with(str(organization_profile_data["id"]))


def test_update_profile(
    authenticated_client,
    updated_organization_profile_data,
    mocker,
):
    mock_update = mocker.patch(
        "app.modules.organizations.profile.router.update_profile",
        return_value=updated_organization_profile_data,
    )

    response = authenticated_client.patch(
        "/organizations/profile",
        json={"name": "Updated Hospital"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Hospital"
    mock_update.assert_called_once_with(
        organization_id=str(ORGANIZATION_ID),
        payload=mocker.ANY,
        actor_id=USER_ID,
        actor_roles=mocker.ANY,
    )


def test_profile_read_denies_when_org_admin_dependency_denies(
    authenticated_client,
):
    def deny():
        raise HTTPException(status_code=403, detail="Organization administrator required")

    app.dependency_overrides[require_current_user_organization_admin] = deny

    response = authenticated_client.get("/organizations/profile")

    assert response.status_code == 403
