from main import app
from app.modules.organizations.dependencies import require_organization_access

import pytest

from uuid import uuid4

from fastapi import status

from app.modules.organizations.departments import router
from app.modules.organizations.departments.schemas import (
    DepartmentResponse,
)
from app.modules.organizations.departments.exceptions import (
    DepartmentAlreadyExistsError,
    InvalidParentDepartmentError,
    CircularDepartmentHierarchyError,
    DepartmentHasChildrenError,
)
from app.modules.organizations.exceptions import DepartmentNotFoundError



ORGANIZATION_ID = uuid4()

BASE_URL = (
    f"/organizations/{ORGANIZATION_ID}/departments"
)


# ----------------------------
# CREATE DEOARTMENT ROUTE TEST
# ----------------------------
def test_create_department_success(
    authenticated_client,
    authenticated_user,
    mocker,
    create_payload,
    department_data,
):
    create = mocker.patch.object(
        router,
        "create_department_service",
        return_value=DepartmentResponse.model_validate(
            department_data
        ),
    )

    response = authenticated_client.post(
        BASE_URL,
        json=create_payload.model_dump(
            mode="json",
            exclude_none=True,
        ),
    )

    assert response.status_code == status.HTTP_201_CREATED

    body = response.json()

    assert body["id"] == str(
        department_data["id"]
    )

    assert body["name"] == department_data["name"]

    create.assert_called_once()

    _, kwargs = create.call_args

    assert kwargs["organization_id"] == ORGANIZATION_ID

    assert kwargs["actor_id"] == authenticated_user["id"]

    assert kwargs["payload"].name == create_payload.name


# ----------------------------------------
# CREATE DEOARTMENT REQUIREMENT ROUTE TEST
# ----------------------------------------
def test_create_department_requires_authentication(
    client,
    create_payload,
):
    response = client.post(
        BASE_URL,
        json=create_payload.model_dump(
            mode="json",
            exclude_none=True,
        ),
    )

    assert (
        response.status_code
        == status.HTTP_401_UNAUTHORIZED
    )


# --------------------------------------------
# CREATE DEOARTMENT INVALID PAYLOAD ROUTE TEST
# --------------------------------------------
def test_create_department_invalid_payload(
    authenticated_client,
):
    response = authenticated_client.post(
        BASE_URL,
        json={},
    )

    assert (
        response.status_code
        == status.HTTP_422_UNPROCESSABLE_ENTITY
    )


# --------------------------------------------
# CREATE DUPLICATE DEOARTMENT NAME ROUTER TEST
# --------------------------------------------
def test_create_department_duplicate_name(
    authenticated_client,
    mocker,
    create_payload,
):
    mocker.patch.object(
        router,
        "create_department_service",
        side_effect=DepartmentAlreadyExistsError(),
    )

    response = authenticated_client.post(
        BASE_URL,
        json=create_payload.model_dump(
            mode="json",
            exclude_none=True,
        ),
    )

    assert (
        response.status_code
        == status.HTTP_409_CONFLICT
    )


# --------------------------------------------
# VERIFY JSON CONTRACT / SHAPE
# --------------------------------------------
def test_create_department_response_contract(
    authenticated_client,
    mocker,
    create_payload,
    department_data,
):
    mocker.patch.object(
        router,
        "create_department_service",
        return_value=DepartmentResponse.model_validate(
            department_data
        ),
    )

    response = authenticated_client.post(
        BASE_URL,
        json=create_payload.model_dump(
            mode="json",
            exclude_none=True,
        ),
    )

    body = response.json()

    expected = {
        "id",
        "organization_id",
        "parent_department_id",
        "name",
        "code",
        "description",
        "active",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    }

    assert expected.issubset(body.keys())


# --------------------------------
# LIST DEPARTMENTS ROUTE TEST
# --------------------------------
def test_list_departments_success(
    authenticated_client,
    mocker,
    department_data,
):
    departments = [
        DepartmentResponse.model_validate(department_data)
    ]

    list_service = mocker.patch.object(
        router,
        "list_departments_service",
        return_value=departments,
    )

    response = authenticated_client.get(BASE_URL)

    assert response.status_code == status.HTTP_200_OK

    body = response.json()

    assert isinstance(body, list)

    assert len(body) == 1

    assert body[0]["id"] == str(
        department_data["id"]
    )

    list_service.assert_called_once_with(
        organization_id=ORGANIZATION_ID,
    )


# --------------------------------
# EMPTY LIST ROUTE TEST
# --------------------------------
def test_list_departments_empty(
    authenticated_client,
    mocker,
):
    mocker.patch.object(
        router,
        "list_departments_service",
        return_value=[],
    )

    response = authenticated_client.get(BASE_URL)

    assert response.status_code == status.HTTP_200_OK

    assert response.json() == []


# --------------------------------
# LIST AUTH REQUIRED ROUTE TEST
# --------------------------------
def test_list_departments_requires_authentication(
    client,
):
    response = client.get(BASE_URL)

    assert (
        response.status_code
        == status.HTTP_401_UNAUTHORIZED
    )


# --------------------------------
# GET DEPARTMENT ROUTE TEST
# --------------------------------
def test_get_department_success(
    authenticated_client,
    mocker,
    department_data,
):
    get_service = mocker.patch.object(
        router,
        "get_department_service",
        return_value=DepartmentResponse.model_validate(
            department_data
        ),
    )

    response = authenticated_client.get(
        f"{BASE_URL}/{department_data['id']}"
    )

    assert response.status_code == status.HTTP_200_OK

    body = response.json()

    assert body["id"] == str(
        department_data["id"]
    )

    get_service.assert_called_once_with(
        organization_id=ORGANIZATION_ID,
        department_id=department_data["id"],
    )


# --------------------------------
# GET DEPARTMENT NOT FOUND
# --------------------------------
def test_get_department_not_found(
    authenticated_client,
    mocker,
):
    mocker.patch.object(
        router,
        "get_department_service",
        side_effect=DepartmentNotFoundError(),
    )

    response = authenticated_client.get(
        f"{BASE_URL}/{uuid4()}"
    )

    assert (
        response.status_code
        == status.HTTP_404_NOT_FOUND
    )


# --------------------------------
# GET AUTH REQUIRED
# --------------------------------
def test_get_department_requires_authentication(
    client,
):
    response = client.get(
        f"{BASE_URL}/{uuid4()}"
    )

    assert (
        response.status_code
        == status.HTTP_401_UNAUTHORIZED
    )


# --------------------------------
# UPDATE DEPARTMENT ROUTE TEST
# --------------------------------
def test_update_department_success(
    authenticated_client,
    authenticated_user,
    mocker,
    update_payload,
    updated_department_data,
):
    update = mocker.patch.object(
        router,
        "update_department_service",
        return_value=DepartmentResponse.model_validate(
            updated_department_data
        ),
    )

    response = authenticated_client.patch(
        f"{BASE_URL}/{updated_department_data['id']}",
        json=update_payload.model_dump(
            mode="json",
            exclude_none=True,
        ),
    )

    assert response.status_code == status.HTTP_200_OK

    body = response.json()

    assert body["name"] == updated_department_data["name"]

    update.assert_called_once()

    _, kwargs = update.call_args

    assert kwargs["organization_id"] == ORGANIZATION_ID
    assert kwargs["department_id"] == updated_department_data["id"]
    assert kwargs["actor_id"] == authenticated_user["id"]
    assert kwargs["payload"].name == update_payload.name


# --------------------------------
# UPDATE AUTH REQUIRED
# --------------------------------
def test_update_department_requires_authentication(
    client,
    update_payload,
):
    response = client.patch(
        f"{BASE_URL}/{uuid4()}",
        json=update_payload.model_dump(
            mode="json",
            exclude_none=True,
        ),
    )

    assert (
        response.status_code
        == status.HTTP_401_UNAUTHORIZED
    )


# --------------------------------
# UPDATE INVALID PAYLOAD
# --------------------------------
def test_update_department_invalid_payload(
    authenticated_client,
):
    response = authenticated_client.patch(
        f"{BASE_URL}/{uuid4()}",
        json={
            "active": "not-a-boolean",
        },
    )

    assert (
        response.status_code
        == status.HTTP_422_UNPROCESSABLE_ENTITY
    )


# --------------------------------
# UPDATE NOT FOUND
# --------------------------------
def test_update_department_not_found(
    authenticated_client,
    mocker,
    update_payload,
):
    mocker.patch.object(
        router,
        "update_department_service",
        side_effect=DepartmentNotFoundError(),
    )

    response = authenticated_client.patch(
        f"{BASE_URL}/{uuid4()}",
        json=update_payload.model_dump(
            mode="json",
            exclude_none=True,
        ),
    )

    assert (
        response.status_code
        == status.HTTP_404_NOT_FOUND
    )


# --------------------------------
# UPDATE DUPLICATE NAME
# --------------------------------
def test_update_department_duplicate_name(
    authenticated_client,
    mocker,
    update_payload,
):
    mocker.patch.object(
        router,
        "update_department_service",
        side_effect=DepartmentAlreadyExistsError(),
    )

    response = authenticated_client.patch(
        f"{BASE_URL}/{uuid4()}",
        json=update_payload.model_dump(
            mode="json",
            exclude_none=True,
        ),
    )

    assert (
        response.status_code
        == status.HTTP_409_CONFLICT
    )


# --------------------------------
# UPDATE INVALID PARENT
# --------------------------------
def test_update_department_invalid_parent(
    authenticated_client,
    mocker,
):
    payload = {
        "parent_department_id": str(uuid4()),
    }

    mocker.patch.object(
        router,
        "update_department_service",
        side_effect=InvalidParentDepartmentError(),
    )

    response = authenticated_client.patch(
        f"{BASE_URL}/{uuid4()}",
        json=payload,
    )

    assert (
        response.status_code
        == status.HTTP_400_BAD_REQUEST
    )


# --------------------------------
# UPDATE CIRCULAR HIERARCHY
# --------------------------------
def test_update_department_circular_reference(
    authenticated_client,
    mocker,
):
    payload = {
        "parent_department_id": str(uuid4()),
    }

    mocker.patch.object(
        router,
        "update_department_service",
        side_effect=CircularDepartmentHierarchyError(),
    )

    response = authenticated_client.patch(
        f"{BASE_URL}/{uuid4()}",
        json=payload,
    )

    assert (
        response.status_code
        == status.HTTP_400_BAD_REQUEST
    )


# --------------------------------
# UPDATE RESPONSE CONTRACT
# --------------------------------
def test_update_department_response_contract(
    authenticated_client,
    mocker,
    update_payload,
    updated_department_data,
):
    mocker.patch.object(
        router,
        "update_department_service",
        return_value=DepartmentResponse.model_validate(
            updated_department_data
        ),
    )

    response = authenticated_client.patch(
        f"{BASE_URL}/{updated_department_data['id']}",
        json=update_payload.model_dump(
            mode="json",
            exclude_none=True,
        ),
    )

    body = response.json()

    expected = {
        "id",
        "organization_id",
        "parent_department_id",
        "name",
        "code",
        "description",
        "active",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    }

    assert expected.issubset(body.keys())


# --------------------------------
# DELETE DEPARTMENT ROUTE TEST
# --------------------------------
def test_delete_department_success(
    authenticated_client,
    authenticated_user,
    mocker,
    department_data,
):
    delete = mocker.patch.object(
        router,
        "delete_department_service",
    )

    response = authenticated_client.delete(
        f"{BASE_URL}/{department_data['id']}"
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert response.content == b""

    delete.assert_called_once_with(
        organization_id=ORGANIZATION_ID,
        department_id=department_data["id"],
        actor_id=authenticated_user["id"],
    )


# --------------------------------
# DELETE AUTH REQUIRED
# --------------------------------
def test_delete_department_requires_authentication(
    client,
):
    response = client.delete(
        f"{BASE_URL}/{uuid4()}"
    )

    assert (
        response.status_code
        == status.HTTP_401_UNAUTHORIZED
    )


# --------------------------------
# DELETE NOT FOUND
# --------------------------------
def test_delete_department_not_found(
    authenticated_client,
    mocker,
):
    mocker.patch.object(
        router,
        "delete_department_service",
        side_effect=DepartmentNotFoundError(),
    )

    response = authenticated_client.delete(
        f"{BASE_URL}/{uuid4()}"
    )

    assert (
        response.status_code
        == status.HTTP_404_NOT_FOUND
    )


# --------------------------------
# DELETE HAS CHILDREN
# --------------------------------
def test_delete_department_has_children(
    authenticated_client,
    mocker,
):
    mocker.patch.object(
        router,
        "delete_department_service",
        side_effect=DepartmentHasChildrenError(),
    )

    response = authenticated_client.delete(
        f"{BASE_URL}/{uuid4()}"
    )

    assert (
        response.status_code
        == status.HTTP_409_CONFLICT
    )

def test_list_departments_denies_without_organization_configuration_authority(
    authenticated_client,
    mocker,
):
    from fastapi import HTTPException

    def deny():
        raise HTTPException(status_code=403, detail="Organization administrator required")

    app.dependency_overrides[require_organization_access] = deny
    list_service = mocker.patch.object(router, "list_departments_service")

    response = authenticated_client.get(BASE_URL)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    list_service.assert_not_called()


def test_get_department_denies_without_organization_configuration_authority(
    authenticated_client,
    mocker,
):
    from fastapi import HTTPException

    def deny():
        raise HTTPException(status_code=403, detail="Organization administrator required")

    app.dependency_overrides[require_organization_access] = deny
    get_service = mocker.patch.object(router, "get_department_service")

    response = authenticated_client.get(f"{BASE_URL}/{uuid4()}")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    get_service.assert_not_called()
