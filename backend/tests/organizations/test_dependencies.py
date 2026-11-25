import pytest
from uuid import uuid4
from tests.factories.user import user_factory
from app.modules.organizations import dependencies
from app.modules.organizations.exceptions import (
    OrganizationAccessDeniedError,
    OrganizationNotFoundError,
)
from tests.factories.organization import (
    organization_factory,
)
from tests.factories.constants import (
    ORGANIZATION_ID,
    OTHER_ORGANIZATION_ID,
    USER_ID
)




# ---------------------------------------------------------
# USER ORGANIZATION ACCESS DEPENDENCY TEST
# ---------------------------------------------------------
def test_user_has_organization_access_returns_true():
    current_user = user_factory(
        organization_ids=[
            str(ORGANIZATION_ID),
        ]
    )

    result = dependencies._user_has_organization_access(
        current_user=current_user,
        organization_id=ORGANIZATION_ID,
    )

    assert result is True


def test_user_has_organization_access_returns_false_for_other_organization():
    current_user = user_factory(
        organization_ids=[
            str(ORGANIZATION_ID),
        ]
    )

    result = dependencies._user_has_organization_access(
        current_user=current_user,
        organization_id=OTHER_ORGANIZATION_ID,
    )

    assert result is False


def test_user_has_organization_access_supports_multiple_organizations():
    third_organization_id = uuid4()

    current_user = user_factory(
        organization_ids=[
            str(ORGANIZATION_ID),
            str(OTHER_ORGANIZATION_ID),
        ]
    )

    assert dependencies._user_has_organization_access(
        current_user=current_user,
        organization_id=ORGANIZATION_ID,
    ) is True

    assert dependencies._user_has_organization_access(
        current_user=current_user,
        organization_id=OTHER_ORGANIZATION_ID,
    ) is True

    assert dependencies._user_has_organization_access(
        current_user=current_user,
        organization_id=third_organization_id,
    ) is False


# def test_user_has_organization_access_returns_false_when_organization_ids_missing():
#     current_user = user_factory(
#         organization_ids=None,
#     )

#     result = dependencies._user_has_organization_access(
#         current_user=current_user,
#         organization_id=ORGANIZATION_ID,
#     )

#     assert result is False


def test_user_has_organization_access_returns_false_when_organization_ids_empty():
    current_user = user_factory(
        organization_ids=[],
    )

    result = dependencies._user_has_organization_access(
        current_user=current_user,
        organization_id=ORGANIZATION_ID,
    )

    assert result is False


def test_user_has_organization_access_normalizes_uuid_values():
    current_user = user_factory(
        organization_ids=[
            ORGANIZATION_ID,
        ]
    )

    result = dependencies._user_has_organization_access(
        current_user=current_user,
        organization_id=ORGANIZATION_ID,
    )

    assert result is True


# ---------------------------------------------------------
# REQUIRE ORGANIZATION ACCESS DEPENDENCY TEST
# ---------------------------------------------------------
def test_require_organization_access_returns_organization(
    organization= organization_factory,
):
    result = dependencies.require_organization_access(
        organization=organization,
    )

    assert result is organization



# ---------------------------------------------------------
# ORGANIZATION MEMBER DEPENDENCY TEST
# ---------------------------------------------------------


def test_require_organization_member_returns_organization(
    mocker,
):
    organization = organization_factory()

    get_organization = mocker.patch.object(
        dependencies,
        "get_organization",
        return_value=organization,
    )

    current_user = user_factory(
        organization_ids=[
            str(ORGANIZATION_ID),
        ]
    )

    result = dependencies.require_organization_member(
        organization_id=ORGANIZATION_ID,
        current_user=current_user,
    )

    assert result is organization

    get_organization.assert_called_once_with(
        organization_id=str(ORGANIZATION_ID),
    )


def test_require_organization_member_raises_not_found(
    mocker,
):
    mocker.patch.object(
        dependencies,
        "get_organization",
        side_effect=OrganizationNotFoundError(),
    )

    current_user = user_factory(
        organization_ids=[
            str(ORGANIZATION_ID),
        ]
    )

    with pytest.raises(
        OrganizationNotFoundError
    ):
        dependencies.require_organization_member(
            organization_id=ORGANIZATION_ID,
            current_user=current_user,
        )


def test_require_organization_member_raises_access_denied(
    mocker,
):
    organization = organization_factory()

    mocker.patch.object(
        dependencies,
        "get_organization",
        return_value=organization,
    )

    current_user = user_factory(
        organization_ids=[
            str(OTHER_ORGANIZATION_ID),
        ]
    )

    with pytest.raises(
        OrganizationAccessDeniedError
    ):
        dependencies.require_organization_member(
            organization_id=ORGANIZATION_ID,
            current_user=current_user,
        )