from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.auth import role_assignment_service as service


def _role_query(mocker, role):
    query = mocker.Mock()
    for method in ("select", "eq", "is_", "maybe_single"):
        getattr(query, method).return_value = query
    query.execute.return_value = mocker.Mock(data=role)
    return query


def _org_admin(org_id):
    return [{
        "name": "org_admin",
        "role_type": "organization",
        "organization_id": org_id,
        "category": "organization_administrator",
    }]


def test_grant_calls_trusted_rpc_with_actor_and_reason(mocker):
    actor_id, target_id, org_id, role_id = [str(uuid4()) for _ in range(4)]
    role = {
        "id": role_id,
        "name": "practitioner",
        "role_type": "organization",
        "organization_id": org_id,
        "is_active": True,
    }
    admin = mocker.patch.object(service, "supabase_admin")
    admin.table.return_value = _role_query(mocker, role)
    admin.auth.admin.get_user_by_id.return_value = mocker.Mock(
        user=mocker.Mock(id=target_id)
    )
    rpc_query = mocker.Mock()
    rpc_query.execute.return_value = mocker.Mock(data={"status": "active"})
    admin.rpc.return_value = rpc_query

    result = service.assign_organization_role(
        actor_id=actor_id,
        actor_roles=_org_admin(org_id),
        target_user_id=target_id,
        role_name="practitioner",
        organization_id=org_id,
        reason="approved staff onboarding",
    )

    assert result == {"status": "active"}
    admin.rpc.assert_called_once_with(
        "change_user_role_assignment",
        {
            "p_user_id": target_id,
            "p_role_id": role_id,
            "p_organization_id": org_id,
            "p_actor_id": actor_id,
            "p_actor_type": "user",
            "p_action": "assign",
            "p_reason": "approved staff onboarding",
        },
    )


def test_self_grant_is_rejected_before_rpc(mocker):
    actor_id, org_id = str(uuid4()), str(uuid4())
    role = {
        "id": str(uuid4()),
        "name": "practitioner",
        "role_type": "organization",
        "organization_id": org_id,
        "is_active": True,
    }
    admin = mocker.patch.object(service, "supabase_admin")
    admin.table.return_value = _role_query(mocker, role)

    with pytest.raises(HTTPException) as error:
        service.assign_organization_role(
            actor_id=actor_id,
            actor_roles=_org_admin(org_id),
            target_user_id=actor_id,
            role_name="practitioner",
            organization_id=org_id,
        )

    assert error.value.status_code == 403
    admin.auth.admin.get_user_by_id.assert_not_called()
    admin.rpc.assert_not_called()


def test_revoke_requires_reason_and_records_revoke_action(mocker):
    actor_id, target_id, org_id, role_id = [str(uuid4()) for _ in range(4)]
    role = {
        "id": role_id,
        "name": "practitioner",
        "role_type": "organization",
        "organization_id": org_id,
        "is_active": True,
    }
    admin = mocker.patch.object(service, "supabase_admin")
    admin.table.return_value = _role_query(mocker, role)
    admin.auth.admin.get_user_by_id.return_value = mocker.Mock(
        user=mocker.Mock(id=target_id)
    )
    rpc_query = mocker.Mock()
    rpc_query.execute.return_value = mocker.Mock(data={"status": "revoked"})
    admin.rpc.return_value = rpc_query

    service.revoke_organization_role(
        actor_id=actor_id,
        actor_roles=_org_admin(org_id),
        target_user_id=target_id,
        role_name="practitioner",
        organization_id=org_id,
        reason="employment ended",
    )

    assert admin.rpc.call_args.args[0] == "change_user_role_assignment"
    assert admin.rpc.call_args.args[1]["p_action"] == "revoke"
    assert admin.rpc.call_args.args[1]["p_reason"] == "employment ended"

