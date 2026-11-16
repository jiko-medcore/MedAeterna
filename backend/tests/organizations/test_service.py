import pytest
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.modules.organizations import service
from app.modules.organizations.schemas import (
    OrganizationCreate,
    OrganizationUpdate,
    AcceptInviteRequest,
    RoleAssignment,
)
from tests.factories.constants import (
    ORGANIZATION_ID,
    USER_ID,
)


def _mock_query(mocker, data=None):
    query = mocker.Mock()
    for method_name in ("select", "eq", "is_", "in_", "maybe_single", "single", "insert", "update"):
        getattr(query, method_name).return_value = query
    query.execute.return_value = mocker.Mock(data=data)
    return query


def _mock_accept_invitation_dependencies(
    mocker,
    *,
    invite,
    organization_id,
    user_id=str(USER_ID),
    invite_role=None,
    issuer_roles=None,
    signup_user=True,
):
    invitation_query = _mock_query(mocker, invite)
    update_query = _mock_query(mocker, [{"id": invite.get("id"), "status": "accepted"}])
    membership_query = _mock_query(mocker, [{"role_id": "issuer-role"}])
    issuer_role_query = _mock_query(mocker, issuer_roles or [{
        "id": "issuer-role",
        "name": "org_admin",
        "role_type": "organization",
        "organization_id": str(organization_id),
        "is_active": True,
    }])
    target_role_query = _mock_query(mocker, (None if invite_role is False else {
        "id": "target-role",
        "name": "practitioner",
        "role_type": "organization",
        "organization_id": str(organization_id),
        "is_active": True,
    } if invite_role is None else invite_role))
    supabase_admin = mocker.patch.object(service, "supabase_admin")
    table_queues = {
        "invitations": [invitation_query, update_query],
        "user_roles": [membership_query],
        "roles": [issuer_role_query, target_role_query],
    }
    supabase_admin.table.side_effect = lambda name: table_queues[name].pop(0)

    auth_result = mocker.Mock()
    auth_result.user = SimpleNamespace(id=user_id) if signup_user else None
    auth = mocker.Mock()
    auth.sign_up.return_value = auth_result
    supabase = mocker.patch.object(service, "supabase")
    supabase.auth = auth
    assigned = mocker.patch.object(
        service,
        "assign_organization_role",
        return_value={"status": "active"},
    )
    return auth, assigned, supabase_admin


# ============================================================
# CREATE ORGANIZATION SERVICE
# ============================================================

def test_create_organization_success(
    mocker,
    organization_data,
):
    payload = OrganizationCreate(
        name=organization_data["name"],
        type=organization_data["type"],
        email=organization_data["email"],
        phone=organization_data["phone"],
        address=organization_data["address"],
        state=organization_data["state"],
        country=organization_data["country"],
        admin_email="admin@test.com",
        admin_password="password123",
    )

    admin_id = str(USER_ID)

    # ---------------------------------
    # Auth user creation
    # ---------------------------------
    auth_response = mocker.Mock()
    auth_response.user = SimpleNamespace(id=admin_id)

    auth = mocker.Mock()
    auth.admin.create_user.return_value = auth_response

    # ---------------------------------
    # Organization creation
    # ---------------------------------
    organization_response = mocker.Mock()
    organization_response.data = [organization_data]

    organization_query = mocker.Mock()
    organization_query.insert.return_value = organization_query
    organization_query.execute.return_value = organization_response

    # ---------------------------------
    # Default roles creation
    # ---------------------------------
    roles_insert_query = mocker.Mock()
    roles_insert_query.execute.return_value = mocker.Mock(
        data=[
            {"id": "role-admin"},
            {"id": "role-practitioner"},
            {"id": "role-staff"},
        ]
    )

    # ---------------------------------
    # org_admin role lookup
    # ---------------------------------
    role_response = mocker.Mock()
    role_response.data = {"id": "role-admin"}

    roles_lookup_query = mocker.Mock()
    roles_lookup_query.select.return_value = roles_lookup_query
    roles_lookup_query.eq.return_value = roles_lookup_query
    roles_lookup_query.single.return_value = roles_lookup_query
    roles_lookup_query.execute.return_value = role_response

    # ---------------------------------
    # User-role assignment
    # ---------------------------------
    user_role_query = mocker.Mock()
    user_role_query.insert.return_value = user_role_query
    user_role_query.execute.return_value = mocker.Mock(
        data=[
            {
                "user_id": admin_id,
                "role_id": "role-admin",
                "organization_id": organization_data["id"],
            }
        ]
    )

    # ---------------------------------
    # Roles table
    # ---------------------------------
    roles_table = mocker.Mock()
    roles_table.insert.return_value = roles_insert_query
    roles_table.select.return_value = roles_lookup_query

    # ---------------------------------
    # Supabase Admin
    # ---------------------------------
    supabase_admin = mocker.patch.object(
        service,
        "supabase_admin",
    )

    supabase_admin.auth = auth

    def table_side_effect(table_name):
        if table_name == "organizations":
            return organization_query

        if table_name == "roles":
            return roles_table

        if table_name == "user_roles":
            return user_role_query

        raise AssertionError(
            f"Unexpected table: {table_name}"
        )

    supabase_admin.table.side_effect = table_side_effect

    # ---------------------------------
    # Event
    # ---------------------------------
    emit_event = mocker.patch.object(
        service,
        "emit_event",
    )
    assign_onboarding_role = mocker.patch.object(
        service,
        "assign_onboarding_role",
    )

    # ---------------------------------
    # Execute
    # ---------------------------------
    result = service.create_organization(payload)

    # ---------------------------------
    # Result
    # ---------------------------------
    assert result == {
        "message": "Organization registered successfully",
        "organization_id": organization_data["id"],
    }

    # ---------------------------------
    # Auth assertions
    # ---------------------------------
    auth.admin.create_user.assert_called_once_with({
        "email": "admin@test.com",
        "password": "password123",
        "email_confirm": True,
    })

    # ---------------------------------
    # Organization assertions
    # ---------------------------------
    organization_query.insert.assert_called_once_with(
        payload.model_dump(
            exclude={
                "admin_email",
                "admin_password",
            }
        )
    )

    # ---------------------------------
    # Default role assertions
    # ---------------------------------
    roles_table.insert.assert_called_once_with([
        {
            "name": "org_admin",
            "organization_id": organization_data["id"],
            "role_type": "organization",
        },
        {
            "name": "practitioner",
            "organization_id": organization_data["id"],
            "role_type": "organization",
        },
        {
            "name": "staff",
            "organization_id": organization_data["id"],
            "role_type": "organization",
        },
    ])

    # ---------------------------------
    # Role lookup assertions
    # ---------------------------------
    roles_table.select.assert_called_once_with("id")

    roles_lookup_query.eq.assert_any_call(
        "name",
        "org_admin",
    )

    roles_lookup_query.eq.assert_any_call(
        "organization_id",
        organization_data["id"],
    )

    # ---------------------------------
    # User-role assignment assertions
    # ---------------------------------
    assign_onboarding_role.assert_called_once_with(
        target_user_id=admin_id,
        role_name="org_admin",
        organization_id=organization_data["id"],
        actor_id=admin_id,
        reason="Initial organization administrator provisioned at registration",
    )

    # ---------------------------------
    # Event assertions
    # ---------------------------------
    emit_event.assert_called_once_with(
        aggregate_type="organization",
        aggregate_id=organization_data["id"],
        event_type=service.EventTypes.ORGANIZATION_CREATED,
        payload={
            "organization_id": organization_data["id"],
            "admin_user_id": admin_id,
            "organization_name": organization_data["name"],
            "admin_email": "admin@test.com",
        },
    )


def test_create_organization_raises_when_admin_user_creation_fails(
    mocker,
    organization_data,
):
    payload = OrganizationCreate(
        name=organization_data["name"],
        type=organization_data["type"],
        admin_email="admin@test.com",
        admin_password="password123",
    )

    auth_response = mocker.Mock()
    auth_response.user = None

    auth = mocker.Mock()
    auth.admin.create_user.return_value = auth_response

    supabase_admin = mocker.patch.object(
        service,
        "supabase_admin",
    )

    supabase_admin.auth = auth

    with pytest.raises(
        service.HTTPException,
        match="Failed to create admin user",
    ):
        service.create_organization(payload)

    auth.admin.create_user.assert_called_once()


def test_create_organization_raises_when_organization_creation_fails(
    mocker,
    organization_data,
):
    payload = OrganizationCreate(
        name=organization_data["name"],
        type=organization_data["type"],
        admin_email="admin@test.com",
        admin_password="password123",
    )

    auth_response = mocker.Mock()
    auth_response.user = SimpleNamespace(
        id=str(USER_ID)
    )

    auth = mocker.Mock()
    auth.admin.create_user.return_value = auth_response

    organization_response = mocker.Mock()
    organization_response.data = None

    organization_query = mocker.Mock()
    organization_query.insert.return_value = organization_query
    organization_query.execute.return_value = organization_response

    supabase_admin = mocker.patch.object(
        service,
        "supabase_admin",
    )

    supabase_admin.auth = auth
    supabase_admin.table.return_value = organization_query

    with pytest.raises(
        Exception,
        match="Failed to create organization",
    ):
        service.create_organization(payload)


def test_create_organization_raises_when_org_admin_role_not_found(
    mocker,
    organization_data,
):
    payload = OrganizationCreate(
        name=organization_data["name"],
        type=organization_data["type"],
        admin_email="admin@test.com",
        admin_password="password123",
    )

    auth_response = mocker.Mock()
    auth_response.user = SimpleNamespace(
        id=str(USER_ID)
    )

    auth = mocker.Mock()
    auth.admin.create_user.return_value = auth_response

    # ---------------------------------
    # Organization response
    # ---------------------------------
    organization_response = mocker.Mock()
    organization_response.data = [organization_data]

    organization_query = mocker.Mock()
    organization_query.insert.return_value = organization_query
    organization_query.execute.return_value = organization_response

    # ---------------------------------
    # Roles insert
    # ---------------------------------
    roles_insert_query = mocker.Mock()
    roles_insert_query.execute.return_value = mocker.Mock(
        data=[
            {"id": "role-1"},
            {"id": "role-2"},
            {"id": "role-3"},
        ]
    )

    # ---------------------------------
    # Role lookup fails
    # ---------------------------------
    role_response = mocker.Mock()
    role_response.data = None

    roles_lookup_query = mocker.Mock()
    roles_lookup_query.select.return_value = roles_lookup_query
    roles_lookup_query.eq.return_value = roles_lookup_query
    roles_lookup_query.single.return_value = roles_lookup_query
    roles_lookup_query.execute.return_value = role_response

    roles_table = mocker.Mock()
    roles_table.insert.return_value = roles_insert_query
    roles_table.select.return_value = roles_lookup_query

    supabase_admin = mocker.patch.object(
        service,
        "supabase_admin",
    )

    supabase_admin.auth = auth

    def table_side_effect(table_name):
        if table_name == "organizations":
            return organization_query

        if table_name == "roles":
            return roles_table

        raise AssertionError(
            f"Unexpected table: {table_name}"
        )

    supabase_admin.table.side_effect = table_side_effect

    with pytest.raises(
        Exception,
        match="org_admin role not found",
    ):
        service.create_organization(payload)


# ============================================================
# UPDATE ORGANIZATION SERVICE
# ============================================================

def test_update_organization_success(
    mocker,
    organization_data,
    updated_organization_data,
):
    payload = OrganizationUpdate(
        name="Updated Hospital",
    )

    response = mocker.Mock()
    response.data = [updated_organization_data]

    query = mocker.Mock()
    query.update.return_value = query
    query.eq.return_value = query
    query.execute.return_value = response

    supabase = mocker.patch.object(
        service,
        "supabase",
    )

    supabase.table.return_value = query

    result = service.update_organization(
        organization_data["id"],
        payload,
    )

    assert result == updated_organization_data

    supabase.table.assert_called_once_with(
        "organizations"
    )

    query.update.assert_called_once_with({
        "name": "Updated Hospital",
    })

    query.eq.assert_called_once_with(
        "id",
        organization_data["id"],
    )

    query.execute.assert_called_once_with()


def test_update_organization_raises_when_no_fields_provided(
    mocker,
    organization_data,
):
    payload = OrganizationUpdate()

    supabase = mocker.patch.object(
        service,
        "supabase",
    )

    with pytest.raises(
        service.HTTPException,
        match="No fields provided",
    ):
        service.update_organization(
            organization_data["id"],
            payload,
        )

    supabase.table.assert_not_called()


def test_update_organization_raises_when_organization_not_found(
    mocker,
    organization_data,
):
    payload = OrganizationUpdate(
        name="Updated Hospital",
    )

    response = mocker.Mock()
    response.data = None

    query = mocker.Mock()
    query.update.return_value = query
    query.eq.return_value = query
    query.execute.return_value = response

    supabase = mocker.patch.object(
        service,
        "supabase",
    )

    supabase.table.return_value = query

    with pytest.raises(
        service.HTTPException,
        match="Organization not found",
    ):
        service.update_organization(
            organization_data["id"],
            payload,
        )


# ============================================================
# ASSIGN USER ROLE SERVICE
# ============================================================

def test_assign_user_role_success(
    mocker,
    organization_data,
):
    role_data = RoleAssignment(
        user_id=USER_ID,
        role_name="practitioner",
        org_id=str(organization_data["id"]),
    )

    result = {"status": "active", "user_id": str(USER_ID)}
    assign = mocker.patch.object(
        service,
        "assign_organization_role",
        return_value=result,
    )
    actor_roles = [{
        "name": "org_admin",
        "role_type": "organization",
        "organization_id": str(organization_data["id"]),
        "category": "organization_administrator",
    }]

    assert service.assign_user_role(
        role_data,
        actor_id="admin-user",
        actor_roles=actor_roles,
    ) == result
    assign.assert_called_once_with(
        actor_id="admin-user",
        actor_roles=actor_roles,
        target_user_id=str(USER_ID),
        role_name="practitioner",
        organization_id=str(organization_data["id"]),
        reason=None,
    )


def test_assign_user_role_raises_when_role_not_found(
    mocker,
    organization_data,
):
    role_data = RoleAssignment(
        user_id=USER_ID,
        role_name="practitioner",
        org_id=str(organization_data["id"]),
    )

    assign = mocker.patch.object(
        service,
        "assign_organization_role",
        side_effect=service.HTTPException(status_code=404, detail="Role not found"),
    )

    with pytest.raises(
        service.HTTPException,
        match="Role not found",
    ):
        service.assign_user_role(role_data, actor_id="admin", actor_roles=[])
    assign.assert_called_once()


def test_assign_user_role_raises_when_assignment_fails(
    mocker,
    organization_data,
):
    role_data = RoleAssignment(
        user_id=USER_ID,
        role_name="practitioner",
        org_id=str(organization_data["id"]),
    )

    assign = mocker.patch.object(
        service,
        "assign_organization_role",
        side_effect=RuntimeError("Database write failed"),
    )

    with pytest.raises(
        RuntimeError,
        match="Database write failed",
    ):
        service.assign_user_role(role_data, actor_id="admin", actor_roles=[])
    assign.assert_called_once()


# ============================================================
# CREATE INVITATION SERVICE
# ============================================================

def test_create_invitation_success(
    mocker,
    organization_data,
):
    token = "test-invitation-token"

    mocker.patch.object(
        service.uuid,
        "uuid4",
        return_value=token,
    )

    invitation = {
        "id": "invite-1",
        "email": "staff@test.com",
        "organization_id": organization_data["id"],
        "role_name": "practitioner",
        "invited_by": USER_ID,
        "token": token,
    }

    response = mocker.Mock()
    response.data = [invitation]

    invitation_query = mocker.Mock()
    invitation_query.insert.return_value = invitation_query
    invitation_query.execute.return_value = response

    role_response = mocker.Mock(data={
        "id": "role-practitioner",
        "name": "practitioner",
        "role_type": "organization",
        "organization_id": str(organization_data["id"]),
        "is_active": True,
    })
    role_query = mocker.Mock()
    role_query.select.return_value = role_query
    role_query.eq.return_value = role_query
    role_query.maybe_single.return_value = role_query
    role_query.execute.return_value = role_response

    supabase_admin = mocker.patch.object(
        service,
        "supabase_admin",
    )
    supabase_admin.table.side_effect = lambda name: (
        role_query if name == "roles" else invitation_query
    )
    actor_roles = [{
        "name": "org_admin",
        "role_type": "organization",
        "organization_id": str(organization_data["id"]),
        "category": "organization_administrator",
    }]

    result = service.create_invitation(
        organization_data["id"],
        "staff@test.com",
        "practitioner",
        USER_ID,
        actor_roles=actor_roles,
        actor_email="admin@test.com",
    )

    assert result == invitation

    invitation_query.insert.assert_called_once()

    inserted_data = invitation_query.insert.call_args.args[0]

    assert inserted_data["email"] == "staff@test.com"
    assert (
        inserted_data["organization_id"]
        == organization_data["id"]
    )
    assert inserted_data["role_name"] == "practitioner"
    assert inserted_data["invited_by"] == USER_ID
    assert inserted_data["token"] == token
    assert "expires_at" in inserted_data


def test_create_invitation_raises_when_insert_fails(
    mocker,
    organization_data,
):
    mocker.patch.object(
        service.uuid,
        "uuid4",
        return_value="test-token",
    )

    response = mocker.Mock()
    response.data = None

    invitation_query = mocker.Mock()
    invitation_query.insert.return_value = invitation_query
    invitation_query.execute.return_value = response
    role_response = mocker.Mock(data={
        "id": "role-practitioner",
        "name": "practitioner",
        "role_type": "organization",
        "organization_id": str(organization_data["id"]),
        "is_active": True,
    })
    role_query = mocker.Mock()
    role_query.select.return_value = role_query
    role_query.eq.return_value = role_query
    role_query.maybe_single.return_value = role_query
    role_query.execute.return_value = role_response

    supabase_admin = mocker.patch.object(
        service,
        "supabase_admin",
    )
    supabase_admin.table.side_effect = lambda name: (
        role_query if name == "roles" else invitation_query
    )
    actor_roles = [{
        "name": "org_admin",
        "role_type": "organization",
        "organization_id": str(organization_data["id"]),
        "category": "organization_administrator",
    }]

    with pytest.raises(
        Exception,
        match="Failed to create invitation",
    ):
        service.create_invitation(
            organization_data["id"],
            "staff@test.com",
            "practitioner",
            USER_ID,
            actor_roles=actor_roles,
            actor_email="admin@test.com",
        )


# ============================================================
# ACCEPT INVITATION SERVICE
# ============================================================

def test_accept_invitation_success(
    mocker,
    organization_data,
):
    token = "test-token"
    user_id = str(USER_ID)
    org_id = str(organization_data["id"])
    invitation = {
        "id": "invite-1",
        "email": "staff@test.com",
        "organization_id": org_id,
        "role_name": "practitioner",
        "invited_by": str(ORGANIZATION_ID),
        "expires_at": (datetime.now() + timedelta(days=1)).isoformat(),
        "status": "pending",
    }
    auth, assigned, supabase_admin = _mock_accept_invitation_dependencies(
        mocker, invite=invitation, organization_id=org_id, user_id=user_id
    )

    result = service.accept_invitation(
        AcceptInviteRequest(token=token, password="password123")
    )

    assert result == {"message": "Account created successfully", "user_id": user_id}
    auth.sign_up.assert_called_once_with({
        "email": "staff@test.com",
        "password": "password123",
    })
    assigned.assert_called_once()
    supabase_admin.rpc.assert_not_called()


def test_accept_invitation_raises_when_invitation_is_invalid(
    mocker,
):
    payload = AcceptInviteRequest(
        token="invalid-token",
        password="password123",
    )

    invitation_query = _mock_query(mocker, None)
    supabase_admin = mocker.patch.object(service, "supabase_admin")
    supabase_admin.table.return_value = invitation_query

    with pytest.raises(Exception, match="Invalid or expired invitation"):
        service.accept_invitation(payload)


def test_accept_invitation_raises_when_invitation_expired(
    mocker,
    organization_data,
):
    payload = AcceptInviteRequest(
        token="expired-token",
        password="password123",
    )

    invitation = {
        "id": "invite-1",
        "email": "staff@test.com",
        "organization_id": organization_data["id"],
        "role_name": "practitioner",
        "expires_at": (datetime.now() - timedelta(days=1)).isoformat(),
        "status": "pending",
    }
    invitation_query = _mock_query(mocker, invitation)
    supabase_admin = mocker.patch.object(service, "supabase_admin")
    supabase_admin.table.return_value = invitation_query

    with pytest.raises(service.HTTPException, match="Invitation expired"):
        service.accept_invitation(payload)


def test_accept_invitation_raises_when_signup_fails(
    mocker,
    organization_data,
):
    payload = AcceptInviteRequest(
        token="test-token",
        password="password123",
    )

    invitation = {
        "id": "invite-1",
        "email": "staff@test.com",
        "organization_id": organization_data["id"],
        "role_name": "practitioner",
        "invited_by": str(ORGANIZATION_ID),
        "expires_at": (
            datetime.now() + timedelta(days=1)
        ).isoformat(),
        "status": "pending",
    }

    _, _, _ = _mock_accept_invitation_dependencies(
        mocker,
        invite=invitation,
        organization_id=str(organization_data["id"]),
        signup_user=False,
    )

    with pytest.raises(
        Exception,
        match="Signup failed",
    ):
        service.accept_invitation(payload)


def test_accept_invitation_raises_when_role_not_found(
    mocker,
    organization_data,
):
    payload = AcceptInviteRequest(
        token="test-token",
        password="password123",
    )

    invitation = {
        "id": "invite-1",
        "email": "staff@test.com",
        "organization_id": organization_data["id"],
        "role_name": "practitioner",
        "invited_by": str(ORGANIZATION_ID),
        "expires_at": (
            datetime.now() + timedelta(days=1)
        ).isoformat(),
        "status": "pending",
    }

    _mock_accept_invitation_dependencies(
        mocker,
        invite=invitation,
        organization_id=str(organization_data["id"]),
        invite_role=False,
    )

    with pytest.raises(
        Exception,
        match="Invited role no longer exists",
    ):
        service.accept_invitation(payload)
