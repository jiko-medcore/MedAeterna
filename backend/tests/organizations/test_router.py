from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app

from app.core.security import get_current_user
from app.modules.organizations import router
from app.modules.organizations.dependencies import (
    require_organization_admin_for_org_id,
    require_current_user_organization_admin,
)
from app.modules.organizations.exceptions import (
    OrganizationAccessDeniedError,
    OrganizationNotFoundError,
)

from tests.factories.constants import (
    ORGANIZATION_ID,
    USER_ID,
)


# ============================================================
# TEST DATA
# ============================================================


REGISTER_PAYLOAD = {
    "name": "Test Hospital",
    "type": "hospital",
    "email": "admin@test.com",
    "phone": "08012345678",
    "address": "123 Main Street",
    "state": "Lagos",
    "country": "Nigeria",
    "admin_email": "admin@test.com",
    "admin_password": "SecurePassword123!",
}


UPDATE_PAYLOAD = {
    "name": "Updated Hospital",
}


ROLE_PAYLOAD = {
    "user_id": str(USER_ID),
    "role_name": "practitioner",
    "org_id": str(ORGANIZATION_ID),
}


INVITE_PAYLOAD = {
    "email": "staff@test.com",
    "role_name": "practitioner",
    "org_id": str(ORGANIZATION_ID),
}


ACCEPT_INVITE_PAYLOAD = {
    "token": "test-invitation-token",
    "password": "SecurePassword123!",
}


# ============================================================
# HELPERS
# ============================================================


# ============================================================
# ORGANIZATION REGISTRATION
# ============================================================


def test_register_organization_success(
    client,
    mocker,
):
    mocker.patch.object(router, "process_events_task")
    create_organization = mocker.patch.object(
        router,
        "create_organization",
        return_value={
            "message": "Organization registered successfully",
            "organization_id": str(ORGANIZATION_ID),
        },
    )

    response = client.post(
        "/organizations/register",
        json=REGISTER_PAYLOAD,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["message"] == (
        "Organization registered successfully"
    )
    assert body["organization_id"] == str(ORGANIZATION_ID)

    create_organization.assert_called_once()

    payload = create_organization.call_args.args[0]

    assert payload.name == REGISTER_PAYLOAD["name"]
    assert payload.type == REGISTER_PAYLOAD["type"]
    assert payload.email == REGISTER_PAYLOAD["email"]
    assert payload.admin_email == REGISTER_PAYLOAD["admin_email"]
    assert (
        payload.admin_password
        == REGISTER_PAYLOAD["admin_password"]
    )


def test_register_organization_invalid_payload(
    client,
):
    response = client.post(
        "/organizations/register",
        json={
            "name": "Test Hospital",
            "type": "hospital",
            "email": "not-an-email",
            "admin_email": "admin@test.com",
            "admin_password": "SecurePassword123!",
        },
    )

    assert response.status_code == 422


def test_register_organization_service_exception_propagates(
    client,
    mocker,
):
    mocker.patch.object(
        router,
        "create_organization",
        side_effect=HTTPException(
            status_code=400,
            detail="Failed to create admin user",
        ),
    )

    response = client.post(
        "/organizations/register",
        json=REGISTER_PAYLOAD,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Failed to create admin user"
    )


# ============================================================
# GET MY ORGANIZATION
# ============================================================


def test_get_my_organization_success(
    authenticated_client,
    organization_data,
):
    app.dependency_overrides[require_current_user_organization_admin] = lambda: organization_data

    response = authenticated_client.get("/organizations/me")

    assert response.status_code == 200
    expected = organization_data.copy()
    expected["id"] = str(expected["id"])
    assert response.json() == expected


def test_get_my_organization_denies_user_without_admin_scope(
    authenticated_client,
):
    def deny():
        raise OrganizationAccessDeniedError()

    app.dependency_overrides[require_current_user_organization_admin] = deny

    response = authenticated_client.get("/organizations/me")

    assert response.status_code == 403


def test_get_my_organization_not_found(
    authenticated_client,
):
    def missing():
        raise OrganizationNotFoundError("Organization not found.")

    app.dependency_overrides[require_current_user_organization_admin] = missing

    response = authenticated_client.get("/organizations/me")

    assert response.status_code == 404


# ============================================================
# UPLOAD ORGANIZATION LOGO
# ============================================================


def test_upload_organization_logo_success(
    authenticated_client,
    mocker,
):
    expected_path = f"{ORGANIZATION_ID}/logo.png"
    public_url = f"https://storage.test/organization-logos/{expected_path}"

    replace_logo = mocker.patch.object(
        router,
        "replace_logo",
        return_value=(expected_path, public_url),
    )

    admin = mocker.patch.object(router, "supabase_admin")
    organizations_query = Mock()
    organizations_query.update.return_value = organizations_query
    organizations_query.eq.return_value = organizations_query
    organizations_query.execute.return_value = Mock(
        data=[{"id": str(ORGANIZATION_ID), "logo_url": public_url}]
    )
    admin.table.return_value = organizations_query

    content = b"\x89PNG\r\n\x1a\nfake-png"
    response = authenticated_client.post(
        "/organizations/upload-logo",
        files={"file": ("logo.png", content, "image/png")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "Logo uploaded successfully",
        "logo_url": public_url,
    }
    replace_logo.assert_called_once_with(
        organization_id=str(ORGANIZATION_ID),
        content_type="image/png",
        content=content,
    )
    admin.table.assert_called_once_with("organizations")
    organizations_query.update.assert_called_once_with({"logo_url": public_url})
    organizations_query.eq.assert_called_once_with("id", str(ORGANIZATION_ID))
    organizations_query.execute.assert_called_once()


def test_upload_organization_logo_requires_scoped_organization_admin(
    authenticated_client,
    mocker,
):
    def deny():
        raise OrganizationAccessDeniedError()

    app.dependency_overrides[require_current_user_organization_admin] = deny
    admin = mocker.patch.object(router, "supabase_admin")

    response = authenticated_client.post(
        "/organizations/upload-logo",
        files={"file": ("logo.png", b"unused", "image/png")},
    )

    assert response.status_code == 403
    admin.table.assert_not_called()


def test_upload_organization_logo_rejects_forged_content_before_storage_call(
    authenticated_client,
    mocker,
):
    admin = mocker.patch.object(router, "supabase_admin")

    response = authenticated_client.post(
        "/organizations/upload-logo",
        files={"file": ("logo.png", b"not-a-png", "image/png")},
    )

    assert response.status_code == 400
    admin.table.assert_not_called()


def test_upload_organization_logo_requires_authentication(
    client,
):
    response = client.post(
        "/organizations/upload-logo",
        files={"file": ("logo.png", b"fake", "image/png")},
    )

    assert response.status_code == 401


# ============================================================
# UPDATE ORGANIZATION
# ============================================================


def test_update_my_organization_success(
    authenticated_client,
    mocker,
    updated_organization_data,
):
    mock_update = mocker.patch.object(
        router,
        "update_organization",
        return_value=updated_organization_data,
    )

    response = authenticated_client.put(
        "/organizations/update",
        json=UPDATE_PAYLOAD,
    )

    assert response.status_code == 200
    expected = updated_organization_data.copy()
    expected["id"] = str(expected["id"])
    assert response.json() == expected

    mock_update.assert_called_once()
    call_args = mock_update.call_args
    assert call_args.args[0] == str(ORGANIZATION_ID)
    assert call_args.args[1].name == UPDATE_PAYLOAD["name"]


def test_update_my_organization_invalid_payload(
    authenticated_client,
):
    response = authenticated_client.put(
        "/organizations/update",
        json={"email": "not-an-email"},
    )

    assert response.status_code == 422


def test_update_my_organization_denies_non_admin(
    authenticated_client,
):
    def deny():
        raise OrganizationAccessDeniedError()

    app.dependency_overrides[require_current_user_organization_admin] = deny

    response = authenticated_client.put(
        "/organizations/update",
        json=UPDATE_PAYLOAD,
    )

    assert response.status_code == 403


def test_update_my_organization_service_exception_propagates(
    authenticated_client,
    mocker,
):
    mocker.patch.object(
        router,
        "update_organization",
        side_effect=HTTPException(
            status_code=404,
            detail="Organization not found",
        ),
    )

    response = authenticated_client.put(
        "/organizations/update",
        json=UPDATE_PAYLOAD,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Organization not found"


# ============================================================
# ASSIGN USER ROLE
# ============================================================


def test_assign_role_success(
    authenticated_client,
    mocker,
):



    assign_role = mocker.patch.object(
        router,
        "assign_user_role",
        return_value={
            "id": "user-role-1",
            "user_id": str(USER_ID),
            "role_id": "role-1",
            "organization_id": str(ORGANIZATION_ID),
        },
    )

    response = authenticated_client.post(
        f"/organizations/{ORGANIZATION_ID}/assign-role",
        json=ROLE_PAYLOAD,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["user_id"] == str(USER_ID)
    assert body["organization_id"] == str(ORGANIZATION_ID)

    assigned_payload = assign_role.call_args.args[0]
    assert assigned_payload.user_id == USER_ID
    assert assigned_payload.role_name == "practitioner"
    assert assigned_payload.org_id == str(ORGANIZATION_ID)
    assert assign_role.call_args.kwargs["actor_id"] == USER_ID


def test_assign_role_organization_mismatch(
    authenticated_client,
    mocker,
):



    assign_role = mocker.patch.object(
        router,
        "assign_user_role",
    )

    response = authenticated_client.post(
        f"/organizations/{ORGANIZATION_ID}/assign-role",
        json={
            "user_id": str(USER_ID),
            "role_name": "practitioner",
            "org_id": "22222222-2222-2222-2222-222222222222",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Organization mismatch"
    )

    assign_role.assert_not_called()


def test_assign_role_permission_denied(
    authenticated_client,
    mocker,
):

    app.dependency_overrides[require_organization_admin_for_org_id] = (
        lambda org_id: (_ for _ in ()).throw(
            HTTPException(status_code=403, detail="Organization administrator privileges are required.")
        )
    )

    assign_role = mocker.patch.object(
        router,
        "assign_user_role",
    )

    response = authenticated_client.post(
        f"/organizations/{ORGANIZATION_ID}/assign-role",
        json=ROLE_PAYLOAD,
    )

    assert response.status_code == 403
    assert "administrator" in response.json()["detail"].lower()

    assign_role.assert_not_called()


def test_assign_role_invalid_payload(
    authenticated_client,
    mocker,
):



    response = authenticated_client.post(
        f"/organizations/{ORGANIZATION_ID}/assign-role",
        json={
            "user_id": "not-a-uuid",
            "role_name": "practitioner",
            "org_id": str(ORGANIZATION_ID),
        },
    )

    assert response.status_code == 422


# ============================================================
# INVITE USER
# ============================================================


def test_invite_user_success(
    authenticated_client,
    current_user,
    mocker,
):



    mock_create_invitation = mocker.patch.object(
        router,
        "create_invitation",
        return_value={
            "id": "invite-1",
            "email": "staff@test.com",
            "organization_id": str(ORGANIZATION_ID),
            "role_name": "practitioner",
        },
    )

    response = authenticated_client.post(
        f"/organizations/{ORGANIZATION_ID}/invite",
        json=INVITE_PAYLOAD,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["email"] == "staff@test.com"
    assert body["organization_id"] == str(
        ORGANIZATION_ID
    )

    mock_create_invitation.assert_called_once_with(
        str(ORGANIZATION_ID),
        "staff@test.com",
        "practitioner",
        current_user["id"],
        actor_roles=current_user["roles"],
        actor_email=current_user["email"],
    )


def test_invite_user_to_another_organization(
    authenticated_client,
    mocker,
):


    create_invitation = mocker.patch.object(
        router,
        "create_invitation",
    )

    other_org_id = (
        "22222222-2222-2222-2222-222222222222"
    )

    response = authenticated_client.post(
        f"/organizations/{other_org_id}/invite",
        json={
            "email": "staff@test.com",
            "role_name": "practitioner",
            "org_id": other_org_id,
        },
    )

    assert response.status_code == 403

    assert response.status_code == 403

    create_invitation.assert_not_called()


def test_invite_user_permission_denied(
    authenticated_client,
    mocker,
):

    app.dependency_overrides[require_organization_admin_for_org_id] = (
        lambda org_id: (_ for _ in ()).throw(
            HTTPException(status_code=403, detail="Organization administrator privileges are required.")
        )
    )

    create_invitation = mocker.patch.object(
        router,
        "create_invitation",
    )

    response = authenticated_client.post(
        f"/organizations/{ORGANIZATION_ID}/invite",
        json=INVITE_PAYLOAD,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Organization administrator privileges are required."
    )

    create_invitation.assert_not_called()


def test_invite_user_invalid_payload(
    authenticated_client,
    mocker,
):



    response = authenticated_client.post(
        f"/organizations/{ORGANIZATION_ID}/invite",
        json={
            "email": "not-an-email",
            "role_name": "practitioner",
            "org_id": str(ORGANIZATION_ID),
        },
    )

    assert response.status_code == 422


# ============================================================
# ACCEPT INVITATION
# ============================================================


def test_accept_invitation_success(
    client,
    mocker,
):
    accept_invitation = mocker.patch.object(
        router,
        "accept_invitation",
        return_value={
            "message": "Account created successfully",
            "user_id": str(USER_ID),
        },
    )

    response = client.post(
        "/organizations/accept-invite",
        json=ACCEPT_INVITE_PAYLOAD,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["message"] == (
        "Account created successfully"
    )
    assert body["user_id"] == str(USER_ID)

    accept_invitation.assert_called_once()

    payload = accept_invitation.call_args.args[0]

    assert payload.token == (
        ACCEPT_INVITE_PAYLOAD["token"]
    )
    assert payload.password == (
        ACCEPT_INVITE_PAYLOAD["password"]
    )


def test_accept_invitation_invalid_payload(
    client,
):
    response = client.post(
        "/organizations/accept-invite",
        json={
            "token": "",
        },
    )

    assert response.status_code == 422


def test_accept_invitation_service_exception_propagates(
    client,
    mocker,
):
    mocker.patch.object(
        router,
        "accept_invitation",
        side_effect=HTTPException(
            status_code=400,
            detail="Invalid or expired invitation",
        ),
    )

    response = client.post(
        "/organizations/accept-invite",
        json=ACCEPT_INVITE_PAYLOAD,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Invalid or expired invitation"
    )


# ============================================================
# AUTHENTICATION
# ============================================================


@pytest.mark.parametrize(
    "method,url",
    [
        (
            "GET",
            "/organizations/me",
        ),
        (
            "POST",
            "/organizations/upload-logo",
        ),
    ],
)
def test_authenticated_organization_routes_require_authentication(
    client,
    method,
    url,
):
    if method == "GET":
        response = client.get(url)
    else:
        response = client.post(
            url,
            files={
                "file": (
                    "logo.png",
                    b"\x89PNG\r\n\x1a\nfake",
                    "image/png",
                )
            },
        )

    assert response.status_code == 401


# ============================================================
# PERMISSION DEPENDENCY — REAL GUARD
# ============================================================


def test_self_scoped_organization_routes_use_admin_dependency():
    from app.modules.organizations.dependencies import require_current_user_organization_admin

    expected_paths = {
        "/organizations/me",
        "/organizations/update",
        "/organizations/upload-logo",
        "/organizations/profile",
    }
    routes = {
        getattr(route, "path", None): route
        for route in app.routes
        if getattr(route, "path", None)
    }

    for path in expected_paths:
        matching_routes = [
            route for route in app.routes
            if getattr(route, "path", None) == path
        ]
        assert matching_routes, path
        assert any(
            dependency.call is require_current_user_organization_admin
            for route in matching_routes
            for dependency in route.dependant.dependencies
        ), path
