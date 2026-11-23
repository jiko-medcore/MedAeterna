from pytest_mock import MockerFixture
from tests.factories.constants import ORGANIZATION_ID
from tests.factories.user import USER_ID


# ------------------------
# AUTH OVERRIDE
# ------------------------
def override_current_user():
    return {
        "id": "user-123",
        "email": "admin@test.com",
    }


# --------------------------------------
# GET PROFILE
# --------------------------------------
def test_get_profile_authenticated(
    authenticated_client,
    organization_profile_data,
    mocker,
):
    mock_get_org = mocker.patch(
        "app.modules.organizations.profile.router.get_user_organization_id",
        return_value=str(organization_profile_data["id"]),
    )

    mock_get_profile = mocker.patch(
        "app.modules.organizations.profile.router.get_profile",
        return_value=organization_profile_data,
    )

    response = authenticated_client.get(
        "/organizations/profile"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["id"] == str(
        organization_profile_data["id"]
    )
    assert body["name"] == "Test Hospital"

    mock_get_org.assert_called_once_with(USER_ID)
    mock_get_profile.assert_called_once_with(
        str(organization_profile_data["id"])
    )


# --------------------------------------
# UPDATE PROFILE
# --------------------------------------
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
        json={
            "name": "Updated Hospital"
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["name"] == "Updated Hospital"

    mock_update.assert_called_once_with(
        organization_id=str(ORGANIZATION_ID),
        payload=mocker.ANY,
        actor_id=USER_ID,
        actor_roles=mocker.ANY,
    )