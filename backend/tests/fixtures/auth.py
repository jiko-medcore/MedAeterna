import pytest

from fastapi.testclient import TestClient

from main import app

from app.core.security import get_current_user

from app.modules.organizations.dependencies import (
    require_organization_access,
    require_organization_admin,
    require_organization_admin_for_org_id,
)

from tests.factories.user import (
    user_factory,
)

from tests.factories.organization import (
    ORGANIZATION_ID,
)


# --------------------------------------
# CLIENT TEST FIXTURE
# --------------------------------------

@pytest.fixture
def client():
    app.dependency_overrides.clear()

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# --------------------------------------
# CURRENT USER FIXTURE
# --------------------------------------

@pytest.fixture
def current_user():
    return user_factory()


# --------------------------------------
# AUTHENTICATED CLIENT FIXTURE
# --------------------------------------

@pytest.fixture
def authenticated_client(current_user):

    fake_org = {
        "id": str(ORGANIZATION_ID),
        "name": "Test Hospital",
    }

    app.dependency_overrides[get_current_user] = (
        lambda: current_user
    )

    app.dependency_overrides[
        require_organization_access
    ] = lambda: fake_org

    app.dependency_overrides[
        require_organization_admin
    ] = lambda: fake_org

    def organization_admin_for_id(org_id):
        if str(org_id) != str(ORGANIZATION_ID):
            from app.modules.organizations.exceptions import OrganizationAccessDeniedError
            raise OrganizationAccessDeniedError()
        return fake_org

    app.dependency_overrides[
        require_organization_admin_for_org_id
    ] = organization_admin_for_id

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# --------------------------------------
# AUTHENTICATED USER
# --------------------------------------

@pytest.fixture
def authenticated_user(current_user):
    return current_user



# --------------------------------------
# CLEAR DEPENDENCY
# --------------------------------------

@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()

    yield

    app.dependency_overrides.clear()
