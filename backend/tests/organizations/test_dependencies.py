import pytest
from uuid import uuid4
from tests.factories.user import user_factory
from app.modules.organizations import dependencies
from app.modules.organizations.exceptions import (
    OrganizationAccessDeniedError,
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


def test_require_organization_member_returns_membership_context(
    mocker,
):
    get_organization = mocker.patch.object(dependencies, "get_organization")
    current_user = user_factory(organization_ids=[str(ORGANIZATION_ID)])

    result = dependencies.require_organization_member(
        organization_id=ORGANIZATION_ID,
        current_user=current_user,
    )

    assert result == {
        "organization_id": str(ORGANIZATION_ID),
        "is_member": True,
    }
    get_organization.assert_not_called()


def test_require_organization_member_does_not_resolve_organization_existence(
    mocker,
):
    get_organization = mocker.patch.object(dependencies, "get_organization")
    current_user = user_factory(organization_ids=[str(ORGANIZATION_ID)])

    result = dependencies.require_organization_member(
        organization_id=ORGANIZATION_ID,
        current_user=current_user,
    )

    assert result["is_member"] is True
    get_organization.assert_not_called()


def test_require_organization_member_denies_before_any_privileged_lookup(
    mocker,
):
    get_organization = mocker.patch.object(dependencies, "get_organization")
    current_user = user_factory(organization_ids=[str(OTHER_ORGANIZATION_ID)])

    with pytest.raises(OrganizationAccessDeniedError):
        dependencies.require_organization_member(
            organization_id=ORGANIZATION_ID,
            current_user=current_user,
        )

    get_organization.assert_not_called()
