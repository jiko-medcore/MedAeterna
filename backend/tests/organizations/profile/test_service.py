import pytest
from pytest_mock import MockerFixture
from unittest.mock import patch
from app.modules.organizations.profile.service import (
    get_profile,
    update_profile
)
from app.modules.organizations.exceptions import (
    OrganizationNotFoundError,
)
from app.modules.organizations.profile.schemas import (
    OrganizationProfileUpdate,
)


# ------------------
# GET PROFILE TESTS
# ------------------
@patch(
    "app.modules.organizations.profile.service.get_organization_profile"
)
def test_get_profile(mock_get):

    mock_get.return_value = {
        "id": "org1",
        "name": "MedCore",
        "active": True,
        "type": "Hospital",
    }

    profile = get_profile("org1")

    assert profile.name == "MedCore"


# ---------------------------------
# GET ORGANIZATION NOT FOUND TESTS
# ---------------------------------
@patch(
    "app.modules.organizations.profile.service.get_organization_profile"
)
def test_get_profile_not_found(mock_get):

    mock_get.return_value = None

    with pytest.raises(
        OrganizationNotFoundError
    ):
        get_profile("missing")


# ---------------------
# UPDATE PROFILE TESTS
# ---------------------
def test_update_profile(
    organization_data,
    updated_organization_data,
    mocker,
):
    mock_get = mocker.patch(
        "app.modules.organizations.profile.service.get_organization_profile"
    )

    mock_update = mocker.patch(
        "app.modules.organizations.profile.service.update_organization_profile"
    )

    mock_audit = mocker.patch(
        "app.modules.organizations.profile.service.log_audit_event"
    )

    mock_get.return_value = organization_data
    mock_update.return_value = updated_organization_data

    payload = OrganizationProfileUpdate(
        name="Updated Hospital"
    )

    result = update_profile(
        "org1",
        payload,
        actor_id="user1",
        actor_roles=[{
            "name": "org_admin",
            "role_type": "organization",
            "organization_id": "org1",
            "category": "organization_administrator",
        }],
    )
    
    assert result.id == str(
        organization_data["id"]
    )

    assert result.name == "Updated Hospital"

    mock_get.assert_called_once_with("org1")
    mock_update.assert_called_once()
    mock_audit.assert_called_once()