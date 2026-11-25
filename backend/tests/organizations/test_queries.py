import pytest

from app.modules.organizations import queries
from app.modules.organizations.exceptions import OrganizationNotFoundError
from tests.factories.constants import ORGANIZATION_ID
from tests.factories.organization import organization_row_factory


def test_get_organization_success(mocker):
    organization = organization_row_factory()

    response = mocker.Mock()
    response.data = organization

    query = mocker.Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.maybe_single.return_value = query
    query.execute.return_value = response

    supabase_admin = mocker.patch.object(queries, "supabase_admin")
    supabase_admin.table.return_value = query

    result = queries.get_organization(str(ORGANIZATION_ID))

    assert result == organization
    supabase_admin.table.assert_called_once_with("organizations")
    query.select.assert_called_once_with("*")
    query.eq.assert_called_once_with("id", str(ORGANIZATION_ID))
    query.maybe_single.assert_called_once_with()
    query.execute.assert_called_once_with()


def test_get_organization_raises_when_response_is_none(mocker):
    query = mocker.Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.maybe_single.return_value = query
    query.execute.return_value = None

    supabase_admin = mocker.patch.object(queries, "supabase_admin")
    supabase_admin.table.return_value = query

    with pytest.raises(
        OrganizationNotFoundError,
        match=f"Organization {str(ORGANIZATION_ID)} not found.",
    ):
        queries.get_organization(str(ORGANIZATION_ID))


def test_get_organization_raises_when_data_is_missing(mocker):
    response = mocker.Mock()
    response.data = None

    query = mocker.Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.maybe_single.return_value = query
    query.execute.return_value = response

    supabase_admin = mocker.patch.object(queries, "supabase_admin")
    supabase_admin.table.return_value = query

    with pytest.raises(
        OrganizationNotFoundError,
        match=f"Organization {str(ORGANIZATION_ID)} not found.",
    ):
        queries.get_organization(str(ORGANIZATION_ID))
